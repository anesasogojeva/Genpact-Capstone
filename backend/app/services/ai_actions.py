from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationStatus
from app.models.resource import Resource, ResourceType
from app.models.user import User
from app.routers.resources import _enrich_resource
from app.schemas.ai import ChatResourceSummary, ChatResponse
from app.schemas.resource import ResourceOut
from app.services.booking import cancel_reservation, create_reservation
from app.services.ai_colleagues import (
    is_schedule_colleague_lookup,
    lookup_colleague_locations,
    lookup_colleague_schedule,
    resolve_book_for_user,
)

from app.services.ai_intent_fallback import desk_preferences_label
from app.services.ai_dates import parse_flexible_date

INTENT_DATE_REQUIRED = {
    "book_meeting_room",
    "book_desk",
    "search_meeting_rooms",
    "search_desks",
    "find_colleague",
}

INTENT_EXECUTABLE = {
    "book_meeting_room",
    "book_desk",
    "search_meeting_rooms",
    "search_desks",
    "cancel_reservation",
    "find_colleague",
}

FOLLOW_UP_BY_INTENT = {
    "book_meeting_room": "What date do you need the meeting room?",
    "book_desk": "What date do you need the desk?",
    "search_meeting_rooms": "What date should I search meeting rooms for?",
    "search_desks": "What date should I search desks for?",
    "cancel_reservation": "Which date is the reservation you want to cancel?",
    "find_colleague": "Which date should I check?",
}


def _parse_booking_date(raw: str | None, today: date | None = None) -> date | None:
    return parse_flexible_date(raw, today or date.today())


def _parse_time_value(raw: str) -> time | None:
    cleaned = raw.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    return None


def _parse_duration_minutes(raw: str | None) -> int | None:
    if not raw or not raw.strip():
        return None
    value = raw.strip().lower()
    if value.isdigit():
        return int(value)
    parts = value.split()
    if not parts or not parts[0].isdigit():
        return None
    amount = int(parts[0])
    if len(parts) == 1:
        return amount
    unit = parts[1].rstrip("s")
    if unit in ("m", "min", "minute"):
        return amount
    if unit in ("h", "hr", "hour"):
        return amount * 60
    return None


def _parse_time_range(
    time_raw: str | None,
    duration_raw: str | None,
) -> tuple[time | None, time | None]:
    if not time_raw or not time_raw.strip():
        return None, None
    value = time_raw.strip()
    if "-" in value:
        start_raw, end_raw = value.split("-", 1)
        return _parse_time_value(start_raw), _parse_time_value(end_raw)
    start = _parse_time_value(value)
    if not start:
        return None, None
    minutes = _parse_duration_minutes(duration_raw) or 60
    end_dt = datetime.combine(date.today(), start) + timedelta(minutes=minutes)
    return start, end_dt.time()


def _matches_location(resource: Resource, preferred_location: str | None) -> bool:
    if not preferred_location:
        return True
    haystack = " ".join(
        filter(
            None,
            [resource.floor, resource.zone, resource.building, resource.name, resource.amenities],
        )
    ).lower()
    terms = [term.strip().lower() for term in preferred_location.split("|") if term.strip()]
    if not terms:
        return True
    return all(term in haystack for term in terms)


def _desk_availability_message(
    parsed: ChatResponse,
    booking_date: date,
    matched: list[ResourceOut],
    all_desks: list[ResourceOut],
    *,
    action_prefix: str,
) -> ChatResponse:
    date_label = parsed.date or booking_date.isoformat()
    pref_label = desk_preferences_label(parsed.preferred_location)

    if all_desks:
        names = ", ".join(desk.name for desk in all_desks[:5])
        parsed.action = f"{action_prefix}_no_preference_match"
        parsed.confirmation = (
            f"No {pref_label} desk is free for {date_label}. "
            f"Other available desks: {names}."
        )
        parsed.resources = [_summarize_resource(desk) for desk in all_desks[:8]]
    else:
        parsed.action = f"{action_prefix}_no_availability"
        parsed.confirmation = f"No desks are available for {date_label}."
        parsed.resources = []

    parsed.follow_up_question = None
    return parsed


def _resource_matches_equipment(resource: Resource, equipment: list[str]) -> bool:
    if not equipment:
        return True
    amenities = (resource.amenities or "").lower()
    return all(item.lower() in amenities for item in equipment)


def _summarize_resource(resource: ResourceOut) -> ChatResourceSummary:
    return ChatResourceSummary(
        id=resource.id,
        name=resource.name,
        floor=resource.floor,
        zone=resource.zone,
        capacity=resource.capacity,
        is_available=bool(resource.is_available),
    )


def _ensure_required_fields(parsed: ChatResponse) -> ChatResponse:
    intent = (parsed.intent or "").lower()
    if intent not in INTENT_DATE_REQUIRED:
        return parsed
    if is_schedule_colleague_lookup(parsed.date):
        parsed.follow_up_question = None
        return parsed
    if _parse_booking_date(parsed.date):
        parsed.follow_up_question = None
        return parsed
    parsed.follow_up_question = parsed.follow_up_question or FOLLOW_UP_BY_INTENT.get(
        intent,
        "What date do you need?",
    )
    return parsed


def _filter_desks_by_zone(desks: list[ResourceOut], zone: str | None) -> list[ResourceOut]:
    if not zone:
        return desks
    return [desk for desk in desks if desk.zone == zone]


def _handle_near_colleague_desk(
    db: Session,
    user: User,
    parsed: ChatResponse,
    booking_date: date,
) -> tuple[list[ResourceOut], ChatResponse | None]:
    if not parsed.coworker:
        return [], None

    colleagues, error = lookup_colleague_locations(
        db,
        user,
        parsed.coworker,
        parsed.date,
        team_scope=False,
    )
    if error:
        parsed.action = "book_desk_colleague_not_in_office"
        parsed.confirmation = error
        parsed.follow_up_question = None
        return [], parsed

    colleague = colleagues[0]
    parsed.colleagues = [colleague]

    all_desks = _list_resources_with_preference_fallback(
        db,
        user,
        booking_date,
        ResourceType.desk,
        None,
        limit=50,
    )

    if not colleague.in_office:
        names = ", ".join(desk.name for desk in all_desks[:5])
        suffix = f" Available desks on that date: {names}." if names else ""
        parsed.action = "book_desk_colleague_not_in_office"
        parsed.confirmation = (
            f"{colleague.name} is not in the office on {booking_date.isoformat()}, "
            f"so I can't find a desk near them.{suffix}"
        )
        parsed.resources = [_summarize_resource(desk) for desk in all_desks[:8]]
        parsed.follow_up_question = None
        return [], parsed

    near_desks = _filter_desks_by_zone(all_desks, colleague.zone)
    if near_desks:
        return near_desks, None

    names = ", ".join(desk.name for desk in all_desks[:5])
    parsed.action = "book_desk_no_near_colleague"
    parsed.confirmation = (
        f"{colleague.name} is at desk {colleague.desk_name} in {colleague.zone}, "
        f"but no other desks in that zone are free.{f' Other available desks: {names}.' if names else ''}"
    )
    parsed.resources = [_summarize_resource(desk) for desk in all_desks[:8]]
    parsed.follow_up_question = None
    return [], parsed


def _is_ready_to_execute(parsed: ChatResponse) -> bool:
    intent = (parsed.intent or "").lower()
    if intent not in INTENT_EXECUTABLE:
        return False
    if intent in INTENT_DATE_REQUIRED:
        if is_schedule_colleague_lookup(parsed.date):
            return bool(parsed.coworker)
        return _parse_booking_date(parsed.date) is not None
    return True


def _list_resources(
    db: Session,
    user: User,
    booking_date: date,
    resource_type: ResourceType,
    preferred_location: str | None = None,
    people: int | None = None,
    equipment: list[str] | None = None,
    limit: int = 8,
) -> list[ResourceOut]:
    query = db.query(Resource).filter(
        Resource.is_active.is_(True),
        Resource.type == resource_type,
    )
    if people is not None and resource_type == ResourceType.room:
        query = query.filter(Resource.capacity >= people)
    resources = query.order_by(Resource.floor, Resource.name).all()

    results: list[ResourceOut] = []
    for resource in resources:
        if not _matches_location(resource, preferred_location):
            continue
        if equipment and not _resource_matches_equipment(resource, equipment):
            continue
        enriched = _enrich_resource(resource, booking_date, user, db)
        if enriched.is_available and not enriched.is_mine:
            results.append(enriched)
        if len(results) >= limit:
            break
    return results


def _list_resources_with_preference_fallback(
    db: Session,
    user: User,
    booking_date: date,
    resource_type: ResourceType,
    preferred_location: str | None = None,
    people: int | None = None,
    equipment: list[str] | None = None,
    limit: int = 50,
) -> list[ResourceOut]:
    candidates = _list_resources(
        db,
        user,
        booking_date,
        resource_type,
        preferred_location,
        people,
        equipment,
        limit,
    )
    if candidates or not preferred_location:
        return candidates
    return _list_resources(
        db,
        user,
        booking_date,
        resource_type,
        None,
        people,
        equipment,
        limit,
    )


def _book_meeting_room(
    db: Session,
    user: User,
    resource_id: int,
    booking_date: date,
    start_time: time | None,
    end_time: time | None,
) -> Reservation:
    return create_reservation(
        db,
        user,
        resource_id,
        booking_date,
        start_time,
        end_time,
    )


def _book_desk(
    db: Session,
    actor: User,
    target_user: User,
    resource_id: int,
    booking_date: date,
) -> Reservation:
    return create_reservation(
        db,
        target_user,
        resource_id,
        booking_date,
        actor=actor,
    )


def _handle_book_meeting_room(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    booking_date = _parse_booking_date(parsed.date)
    if not booking_date:
        return parsed

    start_time, end_time = _parse_time_range(parsed.time, parsed.duration)
    candidates = _list_resources_with_preference_fallback(
        db,
        user,
        booking_date,
        ResourceType.room,
        parsed.preferred_location,
        parsed.people,
        parsed.equipment,
        limit=50,
    )

    if not candidates:
        parsed.action = "book_meeting_room_no_availability"
        parsed.follow_up_question = (
            "No meeting room matches those requirements for that date. "
            "Try fewer people, different equipment, or another date."
        )
        return parsed

    last_error: str | None = None
    for candidate in candidates:
        try:
            reservation = _book_meeting_room(
                db,
                user,
                candidate.id,
                booking_date,
                start_time,
                end_time,
            )
        except HTTPException as exc:
            last_error = str(exc.detail)
            continue

        parsed.reservation_id = reservation.id
        parsed.reservation_date = reservation.date.isoformat()
        parsed.room_name = candidate.name
        parsed.desk_name = None
        parsed.resources = [
            _summarize_resource(_enrich_resource(
                db.get(Resource, candidate.id),
                booking_date,
                user,
                db,
            ))
        ]
        parsed.action = "booked_meeting_room"
        parsed.follow_up_question = None
        return parsed

    parsed.action = "book_meeting_room_failed"
    parsed.follow_up_question = last_error or "No meeting room could be booked."
    return parsed


def _handle_book_desk(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    booking_date = _parse_booking_date(parsed.date)
    if not booking_date:
        return parsed

    requested_time = bool(parsed.time or parsed.duration)
    parsed.time = None
    parsed.duration = None

    target_user, book_for_error = resolve_book_for_user(db, user, parsed.book_for)
    if book_for_error:
        parsed.action = "book_desk_failed"
        parsed.confirmation = book_for_error
        parsed.follow_up_question = book_for_error if "?" in book_for_error else None
        return parsed

    early_response: ChatResponse | None = None
    if parsed.coworker:
        candidates, early_response = _handle_near_colleague_desk(db, user, parsed, booking_date)
        if early_response is not None and not candidates:
            return early_response
    else:
        if parsed.preferred_location:
            matched = _list_resources(
                db,
                user,
                booking_date,
                ResourceType.desk,
                parsed.preferred_location,
                limit=50,
            )
            all_desks = _list_resources(
                db,
                user,
                booking_date,
                ResourceType.desk,
                None,
                limit=50,
            )
            if not matched:
                return _desk_availability_message(
                    parsed,
                    booking_date,
                    matched,
                    all_desks,
                    action_prefix="book_desk",
                )
            candidates = matched
        else:
            candidates = _list_resources_with_preference_fallback(
                db,
                user,
                booking_date,
                ResourceType.desk,
                None,
                limit=50,
            )

    if not candidates:
        if early_response is not None:
            return early_response
        date_label = parsed.date or booking_date.isoformat()
        parsed.action = "book_desk_no_availability"
        parsed.confirmation = f"No desks are available for {date_label}."
        parsed.follow_up_question = None
        return parsed

    last_error: str | None = None
    for candidate in candidates:
        try:
            reservation = _book_desk(db, user, target_user, candidate.id, booking_date)
        except HTTPException as exc:
            last_error = str(exc.detail)
            continue

        parsed.reservation_id = reservation.id
        parsed.reservation_date = reservation.date.isoformat()
        parsed.room_name = None
        parsed.desk_name = candidate.name
        parsed.resources = [
            _summarize_resource(_enrich_resource(
                db.get(Resource, candidate.id),
                booking_date,
                user,
                db,
            ))
        ]
        parsed.action = "booked_desk"
        parsed.follow_up_question = None
        beneficiary = target_user.full_name if parsed.book_for else None
        if parsed.coworker and parsed.colleagues:
            colleague = parsed.colleagues[0]
            if beneficiary:
                parsed.confirmation = (
                    f"Booked desk {candidate.name} for {beneficiary} near {colleague.name} "
                    f"(desk {colleague.desk_name}, {colleague.zone}) on {booking_date.isoformat()}."
                )
            else:
                parsed.confirmation = (
                    f"Booked desk {candidate.name} near {colleague.name} "
                    f"(desk {colleague.desk_name}, {colleague.zone}) on {booking_date.isoformat()}."
                )
        elif beneficiary:
            parsed.confirmation = (
                f"Booked desk {candidate.name} for {beneficiary} on {booking_date.isoformat()}."
            )
        elif parsed.preferred_location:
            parsed.confirmation = (
                f"Booked desk {candidate.name} ({parsed.preferred_location} preference) "
                f"on {booking_date.isoformat()}."
            )
        if requested_time:
            parsed.confirmation = (
                f"Desk reservations are all-day only. "
                f"Booked desk {candidate.name} for {booking_date.isoformat()} (full day)."
            )
        return parsed

    parsed.action = "book_desk_failed"
    parsed.follow_up_question = last_error or "No desk could be booked."
    return parsed


def _handle_search_meeting_rooms(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    booking_date = _parse_booking_date(parsed.date)
    if not booking_date:
        return parsed

    rooms = _list_resources(
        db,
        user,
        booking_date,
        ResourceType.room,
        parsed.preferred_location,
        parsed.people,
        parsed.equipment,
    )
    parsed.resources = [_summarize_resource(room) for room in rooms]
    parsed.action = "search_meeting_rooms" if rooms else "search_meeting_rooms_empty"
    parsed.follow_up_question = None
    return parsed


def _handle_search_desks(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    booking_date = _parse_booking_date(parsed.date)
    if not booking_date:
        return parsed

    desks = _list_resources(
        db,
        user,
        booking_date,
        ResourceType.desk,
        parsed.preferred_location,
        limit=50,
    )

    date_label = parsed.date or booking_date.isoformat()
    if parsed.coworker:
        colleagues, error = lookup_colleague_locations(
            db,
            user,
            parsed.coworker,
            parsed.date,
            team_scope=False,
        )
        if error:
            parsed.action = "search_desks_empty"
            parsed.confirmation = error
            parsed.follow_up_question = None
            return parsed

        colleague = colleagues[0]
        parsed.colleagues = [colleague]
        if not colleague.in_office:
            parsed.resources = [_summarize_resource(desk) for desk in desks[:8]]
            parsed.action = "search_desks_empty"
            parsed.confirmation = (
                f"{colleague.name} is not in the office on {date_label}, "
                "so I can't filter desks near them."
            )
            parsed.follow_up_question = None
            return parsed

        near_desks = _filter_desks_by_zone(desks, colleague.zone)
        parsed.resources = [_summarize_resource(desk) for desk in near_desks]
        if near_desks:
            names = ", ".join(desk.name for desk in near_desks)
            parsed.confirmation = (
                f"Desks near {colleague.name} (desk {colleague.desk_name}, {colleague.zone}) "
                f"on {date_label}: {names}."
            )
            parsed.action = "search_desks"
        else:
            parsed.action = "search_desks_empty"
            parsed.confirmation = (
                f"No desks in {colleague.zone} are available near {colleague.name} on {date_label}."
            )
        parsed.follow_up_question = None
        return parsed

    if parsed.preferred_location:
        all_desks = _list_resources(
            db,
            user,
            booking_date,
            ResourceType.desk,
            None,
            limit=50,
        )
        if not desks:
            if all_desks:
                return _desk_availability_message(
                    parsed,
                    booking_date,
                    desks,
                    all_desks,
                    action_prefix="search_desks",
                )
            date_label = parsed.date or booking_date.isoformat()
            parsed.action = "search_desks_empty"
            parsed.confirmation = f"No desks are available for {date_label}."
            parsed.follow_up_question = None
            return parsed

    parsed.resources = [_summarize_resource(desk) for desk in desks]
    parsed.action = "search_desks" if desks else "search_desks_empty"
    parsed.follow_up_question = None
    return parsed


def _handle_cancel_reservation(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    booking_date = _parse_booking_date(parsed.date)
    query = (
        db.query(Reservation)
        .filter(
            Reservation.user_id == user.id,
            Reservation.status == ReservationStatus.active,
        )
        .order_by(Reservation.date.asc())
    )
    if booking_date:
        query = query.filter(Reservation.date == booking_date)

    reservation = query.first()
    if not reservation:
        parsed.action = "cancel_reservation_not_found"
        parsed.follow_up_question = None
        if booking_date:
            parsed.reservation_date = booking_date.isoformat()
            parsed.confirmation = (
                f"You don't have any reservations for {booking_date.isoformat()}."
            )
        else:
            parsed.confirmation = "You don't have any upcoming reservations to cancel."
        return parsed

    resource = db.get(Resource, reservation.resource_id)
    try:
        cancel_reservation(db, reservation, user, is_admin=False)
    except HTTPException:
        parsed.action = "cancel_reservation_failed"
        parsed.confirmation = "The reservation could not be cancelled."
        return parsed

    parsed.reservation_id = reservation.id
    parsed.reservation_date = reservation.date.isoformat()
    if resource:
        if resource.type == ResourceType.room:
            parsed.room_name = resource.name
        else:
            parsed.desk_name = resource.name
    parsed.action = "cancelled_reservation"
    parsed.follow_up_question = None
    parsed.confirmation = (
        f"Your {resource.name} reservation for {reservation.date.isoformat()} has been cancelled."
        if resource
        else f"Your reservation for {reservation.date.isoformat()} has been cancelled."
    )
    return parsed


def _format_colleague_confirmation(colleagues) -> str:
    if not colleagues:
        return "No colleague desk information was found."
    lines: list[str] = []
    for colleague in colleagues:
        if colleague.in_office and colleague.desk_name:
            location = f"desk {colleague.desk_name}"
            if colleague.floor:
                location += f" on floor {colleague.floor}"
            lines.append(f"{colleague.name} is in the office on {colleague.date} at {location}.")
        else:
            lines.append(f"{colleague.name} has no desk reservation on {colleague.date}.")
    return " ".join(lines)


def _handle_find_colleague(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    if is_schedule_colleague_lookup(parsed.date):
        colleagues, error, resolved_name = lookup_colleague_schedule(db, parsed.coworker)
        if error:
            parsed.action = "find_colleague_needs_info"
            parsed.confirmation = error
            parsed.follow_up_question = error if "?" in error else None
            return parsed

        parsed.colleagues = colleagues
        parsed.action = "find_colleague" if colleagues else "find_colleague_empty"
        if colleagues:
            parsed.confirmation = _format_colleague_confirmation(colleagues)
        else:
            display_name = resolved_name or parsed.coworker or "That colleague"
            parsed.confirmation = f"{display_name} has no upcoming desk reservations."
        parsed.follow_up_question = None
        return parsed

    booking_date = _parse_booking_date(parsed.date)
    if not booking_date:
        return parsed

    team_scope = not parsed.coworker
    colleagues, error = lookup_colleague_locations(
        db,
        user,
        parsed.coworker,
        parsed.date,
        team_scope=team_scope,
    )

    if error:
        parsed.action = "find_colleague_needs_info"
        parsed.confirmation = error
        parsed.follow_up_question = error if "?" in error else None
        return parsed

    parsed.colleagues = colleagues
    parsed.reservation_date = booking_date.isoformat()
    parsed.action = "find_colleague" if colleagues else "find_colleague_empty"
    parsed.confirmation = _format_colleague_confirmation(colleagues)
    parsed.follow_up_question = None
    return parsed


def apply_intent(db: Session, user: User, parsed: ChatResponse) -> ChatResponse:
    parsed = _ensure_required_fields(parsed)
    if not _is_ready_to_execute(parsed):
        return parsed

    intent = (parsed.intent or "").lower()
    handlers = {
        "book_meeting_room": _handle_book_meeting_room,
        "book_desk": _handle_book_desk,
        "search_meeting_rooms": _handle_search_meeting_rooms,
        "search_desks": _handle_search_desks,
        "cancel_reservation": _handle_cancel_reservation,
        "find_colleague": _handle_find_colleague,
    }
    handler = handlers.get(intent)
    if handler:
        return handler(db, user, parsed)
    return parsed
