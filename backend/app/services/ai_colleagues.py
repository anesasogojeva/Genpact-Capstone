import re
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.reservation import Reservation, ReservationStatus
from app.models.resource import Resource, ResourceType
from app.models.user import User, UserRole
from app.schemas.ai import ColleagueLocationSummary
from app.services.ai_dates import extract_date_phrase, parse_flexible_date

SCHEDULE_DATE_MARKER = "upcoming"

NOT_PERSON_NAMES = {
    "me",
    "my",
    "myself",
    "the",
    "a",
    "team",
    "tomorrow",
    "today",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}

NEAR_LOCATION_TERMS = {
    "window",
    "windows",
    "quiet",
    "entrance",
    "exit",
    "printer",
    "kitchen",
    "coffee",
    "corner",
    "open",
    "balcony",
    "door",
    "lift",
    "elevator",
    "reception",
    "lobby",
}


def _extract_near_term(message: str) -> str | None:
    match = re.search(
        r"\b(?:near|close to)\s+(?:the\s+)?([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)",
        message,
        re.IGNORECASE,
    )
    if not match:
        return None
    term = match.group(1).strip()
    term = re.split(r"\s+for\b", term, flags=re.IGNORECASE)[0].strip()
    return term or None


def is_near_location_term(term: str) -> bool:
    cleaned = term.strip().lower()
    if cleaned in NEAR_LOCATION_TERMS:
        return True
    location_phrases = ("open area", "quiet zone", "window seat")
    return any(phrase in cleaned for phrase in location_phrases)


def _is_person_name(name: str) -> bool:
    cleaned = name.strip().lower()
    if not cleaned:
        return False
    if cleaned in NOT_PERSON_NAMES:
        return False
    if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
        return False
    words = cleaned.split()
    if any(word in NOT_PERSON_NAMES for word in words):
        return False
    if any(word in {"from", "at", "between", "until", "to"} for word in words):
        return False
    if parse_flexible_date(cleaned):
        return False
    return True


def _normalize_book_for_candidate(raw: str) -> str | None:
    name = raw.strip()
    for splitter in (r"\s+from\b", r"\s+on\b", r"\s+at\b", r"\s+between\b"):
        name = re.split(splitter, name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not name:
        return None
    if extract_date_phrase(name) or parse_flexible_date(name):
        return None
    if _is_person_name(name):
        return name
    return None


def _find_users_by_name(db: Session, name: str, limit: int = 5) -> list[User]:
    term = name.strip()
    if not term:
        return []
    return (
        db.query(User)
        .filter(User.full_name.ilike(f"%{term}%"))
        .order_by(User.full_name)
        .limit(limit)
        .all()
    )


def _team_colleagues(db: Session, user: User) -> list[User]:
    if not user.team_name:
        return []
    return (
        db.query(User)
        .filter(
            User.team_name == user.team_name,
            User.id != user.id,
        )
        .order_by(User.full_name)
        .all()
    )


def _desk_reservation(db: Session, user_id: int, booking_date) -> Reservation | None:
    return (
        db.query(Reservation)
        .options(joinedload(Reservation.resource))
        .join(Resource, Reservation.resource_id == Resource.id)
        .filter(
            Reservation.user_id == user_id,
            Reservation.date == booking_date,
            Reservation.status == ReservationStatus.active,
            Resource.type == ResourceType.desk,
        )
        .first()
    )


def _summarize_colleague(person: User, booking_date, reservation: Reservation | None) -> ColleagueLocationSummary:
    resource = reservation.resource if reservation else None
    return ColleagueLocationSummary(
        name=person.full_name,
        date=booking_date.isoformat(),
        in_office=reservation is not None,
        desk_name=resource.name if resource else None,
        floor=resource.floor if resource else None,
        zone=resource.zone if resource else None,
    )


def lookup_colleague_locations(
    db: Session,
    current_user: User,
    coworker: str | None,
    date_raw: str | None,
    *,
    team_scope: bool = False,
) -> tuple[list[ColleagueLocationSummary], str | None]:
    booking_date = parse_flexible_date(date_raw)
    if not booking_date:
        return [], "Which date should I check?"

    if coworker:
        people = _find_users_by_name(db, coworker)
        if len(people) > 1:
            names = ", ".join(person.full_name for person in people)
            return [], f"I found multiple matches: {names}. Please use their full name."
        if not people:
            return [], f"I couldn't find anyone named {coworker.strip()}."
    elif team_scope:
        people = _team_colleagues(db, current_user)
        if not people:
            return [], "You are not assigned to a team, or your team has no other members."
    else:
        return [], "Which colleague should I look up?"

    results: list[ColleagueLocationSummary] = []
    for person in people:
        reservation = _desk_reservation(db, person.id, booking_date)
        results.append(_summarize_colleague(person, booking_date, reservation))

    return results, None


def lookup_colleague_schedule(
    db: Session,
    coworker: str | None,
    *,
    today: date | None = None,
    days_ahead: int | None = None,
) -> tuple[list[ColleagueLocationSummary], str | None, str | None]:
    today = today or date.today()
    horizon = days_ahead if days_ahead is not None else settings.max_booking_days_ahead
    max_date = today + timedelta(days=horizon)

    if not coworker:
        return [], "Which colleague should I look up?", None

    people = _find_users_by_name(db, coworker)
    if len(people) > 1:
        names = ", ".join(person.full_name for person in people)
        return [], f"I found multiple matches: {names}. Please use their full name.", None
    if not people:
        return [], f"I couldn't find anyone named {coworker.strip()}.", None

    person = people[0]
    reservations = (
        db.query(Reservation)
        .options(joinedload(Reservation.resource))
        .join(Resource, Reservation.resource_id == Resource.id)
        .filter(
            Reservation.user_id == person.id,
            Reservation.date >= today,
            Reservation.date <= max_date,
            Reservation.status == ReservationStatus.active,
            Resource.type == ResourceType.desk,
        )
        .order_by(Reservation.date.asc())
        .all()
    )

    results = [
        _summarize_colleague(person, reservation.date, reservation)
        for reservation in reservations
    ]
    return results, None, person.full_name


def is_colleague_schedule_message(message: str) -> bool:
    lower = message.lower()
    return bool(
        re.search(r"\bwhen(?:'s|\s+is|\s+are|\s+does)\b", lower)
        and re.search(r"\b(?:in(?:\s+the)?\s+office|coming(?:\s+in)?|working)\b", lower)
    )


def is_schedule_colleague_lookup(date_raw: str | None) -> bool:
    return bool(date_raw and date_raw.strip().lower() == SCHEDULE_DATE_MARKER)


def extract_book_for_person(message: str) -> str | None:
    text = message.strip()
    patterns = [
        r"(?:book|reserve)\s+(?:a\s+)?(?:desk|seat|spot|workspace)\s+for\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)",
        r"(?:book|reserve)\s+for\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip()
        normalized = _normalize_book_for_candidate(name)
        if normalized:
            return normalized
    return None


def resolve_book_for_user(
    db: Session,
    actor: User,
    book_for_name: str | None,
) -> tuple[User | None, str | None]:
    if not book_for_name:
        return actor, None

    people = _find_users_by_name(db, book_for_name)
    if len(people) > 1:
        names = ", ".join(person.full_name for person in people)
        return None, f"I found multiple matches: {names}. Please use their full name."
    if not people:
        return None, f"I couldn't find anyone named {book_for_name.strip()}."

    target = people[0]
    if actor.role != UserRole.team_leader:
        return None, "Only team leaders can book desks for teammates."
    if target.team_leader_id != actor.id:
        return None, f"{target.full_name} is not on your team."

    return target, None


def is_desk_booking_message(message: str) -> bool:
    lower = message.lower()
    return any(word in lower for word in ("desk", "seat", "spot", "workspace"))


def extract_near_coworker(message: str) -> str | None:
    term = _extract_near_term(message)
    if not term:
        return None
    if term.lower() in {"my", "the", "a", "team"}:
        return None
    if is_near_location_term(term):
        return None
    return term


def extract_near_preferred_location(message: str) -> str | None:
    term = _extract_near_term(message)
    if term and is_near_location_term(term):
        return term.lower()
    return None


def is_near_colleague_desk_message(message: str) -> bool:
    return is_desk_booking_message(message) and extract_near_coworker(message) is not None


def is_book_for_teammate_message(message: str) -> bool:
    return extract_book_for_person(message) is not None


def extract_coworker_name(message: str) -> str | None:
    text = message.strip()
    patterns = [
        r"where is\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)\s+sitting",
        r"where(?:'s|\s+is)\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)\s+(?:on|for|tomorrow|today)",
        r"is\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)\s+(?:on|in the office|in office|sitting|coming)",
        r"when(?:'s|\s+is|\s+are|\s+does)\s+([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)\s+(?:in(?:\s+the)?\s+office|coming|working)",
    ]
    lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name.lower() not in {"my", "the", "a"}:
                return name
    return None


def is_colleague_location_message(message: str) -> bool:
    if is_near_colleague_desk_message(message):
        return False
    lower = message.lower()
    colleague_words = (
        "colleague",
        "colleagues",
        "coworker",
        "coworkers",
        "teammate",
        "teammates",
        "my team",
        "where is",
        "where's",
        "who is in",
        "who's in",
        "sitting",
        "in the office",
        "in office",
    )
    return any(word in lower for word in colleague_words)
