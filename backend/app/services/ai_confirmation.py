from app.schemas.ai import BookingConfirmationFacts
from app.services.huggingface import generate_hf_chat

CONFIRMATION_SYSTEM_PROMPT = """You write friendly DeskDibs booking confirmations.

You receive reservation facts from the backend. Convert them into one or two natural sentences.

Rules:
- Use ONLY the facts provided. Do not invent room names, desk names, dates, or reservation IDs.
- Copy desk_name or room_name EXACTLY as provided.
- Copy reservation_id EXACTLY as provided.
- Do not mention hotels, travel, or email.
- Do not ask follow-up questions.
- Return plain text only. No JSON. No markdown. No bullet points."""


def _fallback_confirmation(facts: BookingConfirmationFacts) -> str:
    if facts.room_name:
        return (
            f"Your meeting room {facts.room_name} is booked for "
            f"{facts.reservation_date} (reservation #{facts.reservation_id})."
        )
    if facts.desk_name:
        return (
            f"Your desk {facts.desk_name} is booked for "
            f"{facts.reservation_date} (reservation #{facts.reservation_id})."
        )
    return (
        f"Your reservation is confirmed for {facts.reservation_date} "
        f"(reservation #{facts.reservation_id})."
    )


def _confirmation_matches_facts(confirmation: str, facts: BookingConfirmationFacts) -> bool:
    if str(facts.reservation_id) not in confirmation:
        return False
    resource_name = facts.room_name or facts.desk_name
    if resource_name and resource_name.lower() not in confirmation.lower():
        return False
    if facts.reservation_date not in confirmation:
        return False
    return True


def _build_confirmation_message(facts: BookingConfirmationFacts) -> str:
    lines = [
        "Convert these reservation facts into a friendly confirmation:",
        f"room_name: {facts.room_name or 'null'}",
        f"desk_name: {facts.desk_name or 'null'}",
        f"reservation_id: {facts.reservation_id}",
        f"reservation_date: {facts.reservation_date}",
    ]
    return "\n".join(lines)


def generate_booking_confirmation(facts: BookingConfirmationFacts) -> str:
    try:
        raw = generate_hf_chat(
            system_prompt=CONFIRMATION_SYSTEM_PROMPT,
            user_message=_build_confirmation_message(facts),
        )
    except Exception:
        return _fallback_confirmation(facts)

    confirmation = raw.strip()
    if not confirmation or not _confirmation_matches_facts(confirmation, facts):
        return _fallback_confirmation(facts)
    return confirmation
