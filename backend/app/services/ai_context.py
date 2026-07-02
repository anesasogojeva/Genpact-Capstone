import json
import re

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.ai import ChatResourceSummary, ChatResponse, ColleagueLocationSummary
from app.services.ai_colleagues import extract_coworker_name, extract_near_coworker, lookup_colleague_locations
from app.services.ai_dates import parse_flexible_date


def parse_last_assistant_response(history: list[dict[str, str]] | None) -> dict | None:
    if not history:
        return None
    for item in reversed(history):
        if item.get("role") != "assistant":
            continue
        content = item.get("content", "").strip()
        if not content.startswith("{"):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def is_proximity_followup(message: str) -> bool:
    lower = message.strip().lower()
    if "near" not in lower:
        return False
    patterns = (
        r"\bare they near\b",
        r"\bwhich ones?(?: are)? near\b",
        r"\bwhich (?:desks|ones)(?: are)? near\b",
        r"\bany(?: of them| of these)? near\b",
        r"\bhow about near\b",
        r"\bis (?:any|one|anyone) near\b",
        r"\bwhich (?:is|are) near\b",
    )
    if any(re.search(pattern, lower) for pattern in patterns):
        return True
    return bool(re.search(r"\b(are they|are any|any of)\b", lower))


def _resources_from_payload(payload: dict) -> list[ChatResourceSummary]:
    resources: list[ChatResourceSummary] = []
    for item in payload.get("resources") or []:
        if not isinstance(item, dict):
            continue
        try:
            resources.append(ChatResourceSummary.model_validate(item))
        except Exception:
            continue
    return resources


def try_proximity_followup(
    db: Session,
    user: User,
    message: str,
    history: list[dict[str, str]] | None,
) -> ChatResponse | None:
    if not is_proximity_followup(message):
        return None

    previous = parse_last_assistant_response(history)
    if not previous:
        return None

    previous_action = (previous.get("action") or "").lower()
    if previous_action not in {"search_desks", "search_desks_empty"}:
        return None

    colleague_name = extract_near_coworker(message) or extract_coworker_name(message)
    if not colleague_name:
        return ChatResponse(
            intent="search_desks",
            action="desk_proximity_followup",
            follow_up_question="Which colleague should I compare desk proximity to?",
        )

    booking_date_raw = previous.get("date") or previous.get("reservation_date")
    booking_date = parse_flexible_date(booking_date_raw)
    if not booking_date:
        return ChatResponse(
            intent="search_desks",
            action="desk_proximity_followup",
            coworker=colleague_name,
            follow_up_question="Which date should I check desk proximity for?",
        )

    listed_desks = _resources_from_payload(previous)
    if not listed_desks:
        return ChatResponse(
            intent="search_desks",
            action="desk_proximity_followup",
            date=booking_date_raw,
            coworker=colleague_name,
            confirmation=f"There were no desks in the previous search to compare near {colleague_name.strip()}.",
        )

    colleagues, error = lookup_colleague_locations(
        db,
        user,
        colleague_name,
        booking_date.isoformat(),
        team_scope=False,
    )
    if error:
        return ChatResponse(
            intent="search_desks",
            action="desk_proximity_followup",
            date=booking_date_raw,
            coworker=colleague_name,
            confirmation=error,
        )

    colleague = colleagues[0]
    date_label = booking_date_raw or booking_date.isoformat()

    if not colleague.in_office:
        return ChatResponse(
            intent="search_desks",
            action="desk_proximity_followup",
            date=date_label,
            coworker=colleague_name,
            colleagues=[colleague],
            resources=listed_desks,
            confirmation=(
                f"{colleague.name} is not in the office on {date_label}, "
                "so I can't tell which desks are near them."
            ),
        )

    near_desks = [desk for desk in listed_desks if desk.zone == colleague.zone]
    far_desks = [desk for desk in listed_desks if desk.zone != colleague.zone]

    near_names = ", ".join(desk.name for desk in near_desks)
    far_names = ", ".join(desk.name for desk in far_desks)
    location = f"desk {colleague.desk_name} in {colleague.zone}"

    if near_desks and far_desks:
        confirmation = (
            f"{colleague.name} is at {location} on {date_label}. "
            f"Near {colleague.name.split()[0]}: {near_names}. "
            f"Not near {colleague.name.split()[0]}: {far_names}."
        )
    elif near_desks:
        confirmation = (
            f"{colleague.name} is at {location} on {date_label}. "
            f"All listed desks ({near_names}) are in the same zone and near {colleague.name.split()[0]}."
        )
    else:
        confirmation = (
            f"{colleague.name} is at {location} on {date_label}. "
            f"None of the listed desks ({far_names}) are in {colleague.zone}."
        )

    return ChatResponse(
        intent="search_desks",
        action="desk_proximity_followup",
        date=date_label,
        coworker=colleague_name,
        colleagues=[colleague],
        resources=near_desks or listed_desks,
        confirmation=confirmation,
    )
