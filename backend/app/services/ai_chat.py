import json
from datetime import date

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.schemas.ai import BookingIntent, BookingConfirmationFacts, BookingIntentType, ChatResponse
from app.services.ai_context import try_proximity_followup
from app.services.ai_actions import apply_intent
from app.services.ai_dates import message_mentions_time
from app.services.ai_intent_fallback import infer_booking_intent_from_message, reconcile_intent_with_message
from app.services.ai_confirmation import generate_booking_confirmation
from app.services.booking import get_booking_limits
from app.services.huggingface import generate_hf_chat

INVALID_AI_RESPONSE = "The AI response was invalid."

SYSTEM_PROMPT = """You are the AI engine for DeskDibs.

DeskDibs is an office workspace reservation platform.

Users can only:
- reserve desks
- reserve meeting rooms
- search desks
- search meeting rooms
- cancel reservations
- find where colleagues are sitting

Never interpret "room" as a hotel.
Never interpret bookings as travel.
Never write emails.
Never answer as a general assistant.
Always return structured JSON.

Use these intent values:
- book_meeting_room (reserve meeting room — user says book/reserve)
- book_desk (reserve desk — user says book/reserve)
- search_meeting_rooms (list available meeting rooms — user asks what is free/available)
- search_desks (list available desks — user asks what is free/available)
- cancel_reservation (cancel reservation)
- find_colleague (where a colleague or team is sitting on a date)

Questions like "what free desks are there tomorrow" or "any quiet desks for tomorrow" are search_desks, NOT book_desk.
"find me a desk near Alex for tomorrow" is book_desk with coworker set — NOT search_desks and NOT preferred_location.
Only use book_desk or book_meeting_room when the user clearly wants to reserve.

Use conversation history for follow-up questions. If the user just searched desks and asks
"are they near Sarah", answer using the listed desks and Sarah's desk zone — do not repeat
the same generic desk search.

Use coworker for a person's name when booking near them or looking up where someone sits.
Use preferred_location for quiet, window, entrance, or floor preferences — not colleague names.
Desk reservations are all-day only. Never set time or duration for book_desk.
Meeting rooms can use time slots.

Use book_for when a team leader books a desk for a teammate (e.g. "book a seat for Jane").
"Reserve a desk for today" uses date today — book_for is only for a teammate name, not a date.
Dates can be today, tomorrow, friday, 10 july, july 10, 07/03/2026, or 2026-07-10.

Output a single JSON object with these keys (null when unknown, [] for empty equipment):
intent, people, date, time, duration, equipment, preferred_location, coworker, book_for, follow_up_question

If required information is missing, do not guess. Set follow_up_question instead.

DeskDibs automatically assigns an available desk or meeting room. Never ask for a desk number, desk name, or room name.

Informal requests like "reserve tomorrow somewhere quiet" mean book_desk with date and preferred_location.

Required fields:
- book_desk: date only
- book_meeting_room: date only
- search_desks: date only
- search_meeting_rooms: date only
- cancel_reservation: date if the user specifies one; otherwise null is fine
- find_colleague: date required for a single-day lookup; coworker for one person, null for whole team
- find_colleague schedule: for "when is Sarah in the office", set date to "upcoming" and coworker to Sarah

Example colleague lookup:

User:
where is Alex sitting tomorrow

Response:
{
"intent":"find_colleague",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":"Alex",
"follow_up_question":null
}

Example colleague schedule lookup:

User:
when is Sarah in the office

Response:
{
"intent":"find_colleague",
"people":null,
"date":"upcoming",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":"Sarah",
"follow_up_question":null
}

Example team lookup:

User:
tell me where my colleagues are sitting on Friday

Response:
{
"intent":"find_colleague",
"people":null,
"date":"friday",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":null,
"follow_up_question":null
}

Example desk booking:

User:
Book a desk for tomorrow

Response:
{
"intent":"book_desk",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":null,
"follow_up_question":null
}

Example meeting room:

User:
Book a meeting room for 8 people tomorrow at 2 PM with a projector.

Response:
{
"intent":"book_meeting_room",
"people":8,
"date":"tomorrow",
"time":"14:00",
"duration":null,
"equipment":["projector"],
"preferred_location":null,
"coworker":null,
"follow_up_question":null
}

Example desk near a colleague:

User:
find me a desk near Alex for tomorrow

Response:
{
"intent":"book_desk",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":"Alex",
"book_for":null,
"follow_up_question":null
}

Example team leader booking for a teammate near another colleague:

User:
book a seat for Jane on 2026-07-10 near Sarah

Response:
{
"intent":"book_desk",
"people":null,
"date":"2026-07-10",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":"Sarah",
"book_for":"Jane",
"follow_up_question":null
}

Example desk search:

User:
what are any quiet free desks for tomorrow

Response:
{
"intent":"search_desks",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":"quiet",
"coworker":null,
"follow_up_question":null
}

Example informal desk booking:

User:
okay reserve for me tomorrow any place where its quiet

Response:
{
"intent":"book_desk",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":"quiet",
"coworker":null,
"follow_up_question":null
}

Example cancel:

User:
Cancel my reservation for tomorrow

Response:
{
"intent":"cancel_reservation",
"people":null,
"date":"tomorrow",
"time":null,
"duration":null,
"equipment":[],
"preferred_location":null,
"coworker":null,
"follow_up_question":null
}

Return ONLY valid JSON. No markdown. No code fences. No explanations. No extra text."""


def _build_user_context(db: Session, user: User) -> str:
    today = date.today()
    limits = get_booking_limits(db, user)

    upcoming = (
        db.query(Reservation)
        .options(joinedload(Reservation.resource))
        .filter(
            Reservation.user_id == user.id,
            Reservation.status == ReservationStatus.active,
            Reservation.date >= today,
        )
        .order_by(Reservation.date.asc())
        .limit(5)
        .all()
    )

    lines = [
        f"User: {user.full_name} ({user.email})",
        f"Role: {user.role.value}",
        f"Team: {user.team_name or 'none'}",
        f"Active reservations: {limits['active_reservations']} of {limits['max_active_reservations']}",
        f"Remaining booking slots: {limits['remaining_slots']}",
        f"Max booking horizon: {limits['max_booking_days_ahead']} days ahead",
    ]

    if upcoming:
        lines.append("Upcoming bookings:")
        for reservation in upcoming:
            resource = reservation.resource
            resource_label = resource.name if resource else f"resource #{reservation.resource_id}"
            resource_type = resource.type.value if resource else "unknown"
            capacity = resource.capacity if resource else "unknown"
            slot = ""
            if reservation.start_time and reservation.end_time:
                slot = f" {reservation.start_time.strftime('%H:%M')}-{reservation.end_time.strftime('%H:%M')}"
            lines.append(
                f"- {reservation.date.isoformat()}{slot}: {resource_label} "
                f"({resource_type}, capacity {capacity})"
            )
    else:
        lines.append("Upcoming bookings: none")

    return "\n".join(lines)


def _json_candidates(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []

    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        sliced = text[start : end + 1]
        if sliced != text:
            candidates.append(sliced)
    return candidates


def parse_booking_intent(raw: str, user_message: str | None = None) -> BookingIntent:
    for candidate in _json_candidates(raw):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        try:
            return BookingIntent.model_validate(payload)
        except ValidationError:
            continue

    if user_message:
        inferred = infer_booking_intent_from_message(user_message)
        if inferred:
            return inferred

    raise HTTPException(status_code=502, detail=INVALID_AI_RESPONSE)


def _attach_response_messages(result: ChatResponse) -> ChatResponse:
    if result.action == "cancel_reservation_not_found":
        if not result.confirmation:
            date_label = result.reservation_date or result.date
            result.confirmation = (
                f"You don't have any reservations for {date_label}."
                if date_label
                else "You don't have any upcoming reservations to cancel."
            )
        result.follow_up_question = None
        return result

    if result.action == "cancelled_reservation":
        if not result.confirmation:
            date_label = result.reservation_date or result.date or "that date"
            resource_label = result.room_name or result.desk_name
            if resource_label:
                result.confirmation = (
                    f"Your {resource_label} reservation for {date_label} has been cancelled."
                )
            else:
                result.confirmation = f"Your reservation for {date_label} has been cancelled."
        return result

    if result.action == "search_desks" and result.resources:
        if not result.confirmation:
            names = ", ".join(resource.name for resource in result.resources)
            date_label = result.date or result.reservation_date or "that date"
            result.confirmation = f"Available desks for {date_label}: {names}."
        result.follow_up_question = None
        return result

    if result.action == "search_meeting_rooms" and result.resources:
        names = ", ".join(resource.name for resource in result.resources)
        date_label = result.date or result.reservation_date or "that date"
        result.confirmation = f"Available meeting rooms for {date_label}: {names}."
        result.follow_up_question = None
        return result

    if result.action == "search_desks_empty":
        if not result.confirmation:
            date_label = result.date or "that date"
            result.confirmation = f"No desks are available for {date_label}."
        result.follow_up_question = None
        return result

    if result.action == "search_meeting_rooms_empty":
        date_label = result.date or "that date"
        result.confirmation = f"No meeting rooms are available for {date_label}."
        result.follow_up_question = None
        return result

    if result.action in (
        "book_desk_colleague_not_in_office",
        "book_desk_no_near_colleague",
        "book_desk_no_availability",
        "book_desk_no_preference_match",
    ):
        result.follow_up_question = None
        return result

    if result.action not in ("booked_meeting_room", "booked_desk"):
        return result
    if result.confirmation:
        return result
    if result.reservation_id is None or not result.reservation_date:
        return result

    facts = BookingConfirmationFacts(
        room_name=result.room_name,
        desk_name=result.desk_name,
        reservation_id=result.reservation_id,
        reservation_date=result.reservation_date,
    )
    result.confirmation = generate_booking_confirmation(facts)
    return result


def generate_chat_reply(
    db: Session,
    user: User,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> ChatResponse:
    context_response = try_proximity_followup(db, user, message, history)
    if context_response:
        return _attach_response_messages(context_response)

    context = _build_user_context(db, user)
    system_prompt = f"{SYSTEM_PROMPT}\n\nUser context for extraction:\n{context}"
    raw = generate_hf_chat(
        system_prompt=system_prompt,
        user_message=message,
        history=history,
    )
    booking_intent = parse_booking_intent(raw, message)
    booking_intent = reconcile_intent_with_message(message, booking_intent)
    if (
        booking_intent.intent == BookingIntentType.book_desk
        and message_mentions_time(message)
        and not booking_intent.time
    ):
        booking_intent.time = "requested"
    result = apply_intent(db, user, booking_intent.to_chat_response())
    return _attach_response_messages(result)
