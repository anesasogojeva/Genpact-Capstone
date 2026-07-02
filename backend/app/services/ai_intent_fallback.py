import re

from app.schemas.ai import BookingIntent, BookingIntentType
from app.services.ai_colleagues import (
    SCHEDULE_DATE_MARKER,
    extract_book_for_person,
    extract_coworker_name,
    extract_near_coworker,
    extract_near_preferred_location,
    is_book_for_teammate_message,
    is_colleague_location_message,
    is_colleague_schedule_message,
    is_desk_booking_message,
    is_near_colleague_desk_message,
    is_near_location_term,
)
from app.services.ai_dates import extract_date_phrase

SEARCH_SIGNALS = (
    "what are",
    "which ",
    "list ",
    "show me",
    "any free",
    "free desk",
    "free desks",
    "free room",
    "free rooms",
    "available desk",
    "available desks",
    "available room",
    "available rooms",
    "are there",
    "do you have",
    "what desks",
    "what rooms",
    "find me",
    "look for",
    "search for",
    "search ",
    "any available",
)


def is_search_message(message: str) -> bool:
    lower = message.strip().lower()
    if not lower:
        return False
    if any(signal in lower for signal in SEARCH_SIGNALS):
        return True
    if re.match(r"^(what|which|are there|do you have)\b", lower):
        return True
    if "?" in message and any(word in lower for word in ("desk", "desks", "room", "rooms", "free", "available")):
        return True
    return False


def is_book_message(message: str) -> bool:
    lower = message.strip().lower()
    book_signals = (
        "book ",
        "reserve ",
        "make a reservation",
        "hold a desk",
        "hold a room",
        "i need a desk",
        "i need a room",
        "find me",
    )
    return any(signal in lower for signal in book_signals)


def _is_list_only_desk_search(message: str) -> bool:
    lower = message.strip().lower()
    list_phrases = (
        "what desks",
        "which desks",
        "what free",
        "which free",
        "list desks",
        "available desks",
        "any free desks",
        "are there any desks",
        "do you have any desks",
        "show me available",
        "show available",
    )
    return any(phrase in lower for phrase in list_phrases)


def _should_book_near_colleague(message: str) -> bool:
    if not extract_near_coworker(message) or not is_desk_booking_message(message):
        return False
    if is_book_message(message) or extract_book_for_person(message):
        return True
    if _is_list_only_desk_search(message):
        return False
    return not is_search_message(message)


def _extract_date(text: str) -> str | None:
    return extract_date_phrase(text)


def _extract_preferred_location(text: str) -> str | None:
    if extract_near_coworker(text):
        return None
    prefs = _extract_desk_preferences(text)
    if not prefs:
        return None
    return "|".join(prefs)


def _extract_desk_preferences(text: str) -> list[str]:
    prefs: list[str] = []
    lower = text.lower()

    quiet_words = ("quiet", "quite", "silence", "silent", "peaceful")
    if any(word in lower for word in quiet_words):
        prefs.append("quiet")

    floor_match = re.search(r"\bfloor\s+(\d+)\b", lower)
    if floor_match:
        prefs.append(f"floor {floor_match.group(1)}")

    location_patterns = (
        r"\bnear\s+(?:the\s+)?([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)",
        r"\bclose to\s+(?:the\s+)?([a-zA-Z][a-zA-Z'\-]*(?:\s+[a-zA-Z][a-zA-Z'\-]*)?)",
    )
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        term = match.group(1).strip()
        term = re.split(r"\s+for\b", term, flags=re.IGNORECASE)[0].strip().lower()
        if not term or term in {"my", "the", "a", "team"}:
            continue
        if is_near_location_term(term) and term not in prefs:
            prefs.append(term)

    return prefs


def desk_preferences_label(raw: str | None) -> str:
    if not raw:
        return "matching your preferences"
    parts = [part.strip().lower() for part in raw.split("|") if part.strip()]
    labels: list[str] = []
    for part in parts:
        if part == "quiet":
            labels.append("quiet")
        elif part.startswith("floor "):
            labels.append(part)
        else:
            labels.append(f"near the {part}")
    if not labels:
        return "matching your preferences"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f" and {labels[-1]}"


def _search_intent_for_message(lower: str) -> BookingIntentType:
    if any(phrase in lower for phrase in ("meeting room", "conference room", "boardroom")):
        return BookingIntentType.search_meeting_rooms
    if re.search(r"\broom\b", lower) and "desk" not in lower and "restroom" not in lower:
        return BookingIntentType.search_meeting_rooms
    return BookingIntentType.search_desks


def infer_booking_intent_from_message(message: str) -> BookingIntent | None:
    text = message.strip()
    if not text:
        return None

    lower = text.lower()
    booking_date = _extract_date(text)
    preferred_location = _extract_preferred_location(text)

    if "cancel" in lower:
        return BookingIntent(
            intent=BookingIntentType.cancel_reservation,
            date=booking_date,
        )

    near_coworker = extract_near_coworker(text)
    book_for = extract_book_for_person(text)
    if _should_book_near_colleague(text):
        if not booking_date:
            return BookingIntent(
                intent=BookingIntentType.book_desk,
                book_for=book_for,
                coworker=near_coworker,
                follow_up_question="What date do you need the desk?",
            )
        return BookingIntent(
            intent=BookingIntentType.book_desk,
            date=booking_date,
            book_for=book_for,
            coworker=near_coworker,
        )

    if book_for and is_desk_booking_message(text) and is_book_message(text):
        if not booking_date:
            return BookingIntent(
                intent=BookingIntentType.book_desk,
                book_for=book_for,
                follow_up_question="What date do you need the desk?",
            )
        return BookingIntent(
            intent=BookingIntentType.book_desk,
            date=booking_date,
            book_for=book_for,
        )

    if is_colleague_schedule_message(text):
        coworker = extract_coworker_name(text)
        if not coworker:
            return BookingIntent(
                intent=BookingIntentType.find_colleague,
                follow_up_question="Which colleague should I look up?",
            )
        return BookingIntent(
            intent=BookingIntentType.find_colleague,
            date=SCHEDULE_DATE_MARKER,
            coworker=coworker,
        )

    if is_colleague_location_message(text):
        coworker = extract_coworker_name(text)
        if not booking_date:
            return BookingIntent(
                intent=BookingIntentType.find_colleague,
                coworker=coworker,
                follow_up_question="Which date should I check?",
            )
        return BookingIntent(
            intent=BookingIntentType.find_colleague,
            date=booking_date,
            coworker=coworker,
        )

    if (
        is_book_message(text)
        and is_desk_booking_message(text)
        and not _is_list_only_desk_search(text)
    ):
        if not booking_date:
            return BookingIntent(
                intent=BookingIntentType.book_desk,
                book_for=book_for,
                preferred_location=preferred_location,
                follow_up_question="What date do you need the desk?",
            )
        return BookingIntent(
            intent=BookingIntentType.book_desk,
            date=booking_date,
            book_for=book_for,
            preferred_location=preferred_location,
        )

    if is_search_message(text):
        intent = _search_intent_for_message(lower)
    elif any(phrase in lower for phrase in ("meeting room", "conference room", "boardroom")):
        intent = BookingIntentType.book_meeting_room
    elif re.search(r"\broom\b", lower) and "desk" not in lower and "restroom" not in lower:
        intent = BookingIntentType.book_meeting_room
    elif is_book_message(text):
        if "room" in lower and "desk" not in lower:
            intent = BookingIntentType.book_meeting_room
        else:
            intent = BookingIntentType.book_desk
    elif any(word in lower for word in ("reserve", "reservation")):
        intent = BookingIntentType.book_desk
    elif any(word in lower for word in ("place", "spot", "anywhere", "any place", "somewhere")):
        intent = BookingIntentType.book_desk
    elif any(word in lower for word in ("desk", "seat", "workspace", "hot desk")):
        intent = BookingIntentType.book_desk
    else:
        return None

    if intent in {
        BookingIntentType.book_desk,
        BookingIntentType.book_meeting_room,
        BookingIntentType.search_desks,
        BookingIntentType.search_meeting_rooms,
    } and not booking_date:
        return BookingIntent(
            intent=intent,
            preferred_location=preferred_location,
            follow_up_question="What date do you need?",
        )

    return BookingIntent(
        intent=intent,
        date=booking_date,
        preferred_location=preferred_location,
        book_for=extract_book_for_person(text),
        coworker=extract_coworker_name(text) or extract_near_coworker(text),
    )


def reconcile_intent_with_message(message: str, intent: BookingIntent) -> BookingIntent:
    if is_near_colleague_desk_message(message) or is_book_for_teammate_message(message):
        inferred = infer_booking_intent_from_message(message)
        if inferred and inferred.intent == BookingIntentType.book_desk:
            return inferred
        if _should_book_near_colleague(message):
            return BookingIntent(
                intent=BookingIntentType.book_desk,
                date=_extract_date(message),
                book_for=extract_book_for_person(message),
                coworker=extract_near_coworker(message),
            )

    if is_colleague_schedule_message(message) or is_colleague_location_message(message):
        inferred = infer_booking_intent_from_message(message)
        if inferred and inferred.intent == BookingIntentType.find_colleague:
            return inferred

    if not is_search_message(message):
        return intent

    inferred = infer_booking_intent_from_message(message)
    if inferred and inferred.intent in {
        BookingIntentType.search_desks,
        BookingIntentType.search_meeting_rooms,
    }:
        return inferred
    return intent
