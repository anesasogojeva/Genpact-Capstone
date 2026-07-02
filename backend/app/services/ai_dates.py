import re
from datetime import date, timedelta

WEEKDAY_INDEX = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

MONTH_INDEX = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_MONTH_PATTERN = "|".join(
    sorted(MONTH_INDEX.keys(), key=len, reverse=True)
)


def _parse_slash_date(raw: str) -> date | None:
    match = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", raw.strip())
    if not match:
        return None
    first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    candidates = [(first, second), (second, first)]
    for day, month in candidates:
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


def _parse_weekday_phrase(raw: str, today: date) -> date | None:
    lower = raw.strip().lower()
    use_next = bool(re.search(
        r"\bnext\s+(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lower,
    ))

    for label, weekday in sorted(WEEKDAY_INDEX.items(), key=lambda item: len(item[0]), reverse=True):
        if not re.search(rf"\b{re.escape(label)}\b", lower):
            continue
        days_ahead = (weekday - today.weekday()) % 7
        if use_next:
            days_ahead += 7 if days_ahead > 0 else 7
        return today + timedelta(days=days_ahead)
    return None


def _infer_year(month: int, day: int, today: date) -> int:
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return today.year
    if candidate < today:
        return today.year + 1
    return today.year


def _parse_named_month_date(raw: str, today: date) -> date | None:
    lower = raw.strip().lower()

    day_first = re.search(
        rf"\b(\d{{1,2}})\s+(?P<month>{_MONTH_PATTERN})(?:\s+(?P<year>20\d{{2}}))?\b",
        lower,
    )
    if day_first:
        day = int(day_first.group(1))
        month = MONTH_INDEX[day_first.group("month")]
        year = (
            int(day_first.group("year"))
            if day_first.group("year")
            else _infer_year(month, day, today)
        )
        try:
            return date(year, month, day)
        except ValueError:
            return None

    month_first = re.search(
        rf"\b(?P<month>{_MONTH_PATTERN})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(?P<year>20\d{{2}}))?\b",
        lower,
    )
    if month_first:
        month = MONTH_INDEX[month_first.group("month")]
        day = int(month_first.group("day"))
        year = (
            int(month_first.group("year"))
            if month_first.group("year")
            else _infer_year(month, day, today)
        )
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def _extract_named_month_phrase(message: str) -> str | None:
    lower = message.lower()
    patterns = (
        rf"\b(?:on|for)\s+(\d{{1,2}}\s+(?:{_MONTH_PATTERN})(?:\s+20\d{{2}})?)\b",
        rf"\b(\d{{1,2}}\s+(?:{_MONTH_PATTERN})(?:\s+20\d{{2}})?)\b",
        rf"\b(?:on|for)\s+((?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s+20\d{{2}})?)\b",
        rf"\b((?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s+20\d{{2}})?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(1).strip()
    return None


def extract_date_phrase(message: str) -> str | None:
    if not message.strip():
        return None
    lower = message.lower()
    if "tomorrow" in lower:
        return "tomorrow"
    if "today" in lower:
        return "today"

    slash_match = re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}", message)
    if slash_match:
        return slash_match.group(0)

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
    if iso_match:
        return iso_match.group(1)

    named_month = _extract_named_month_phrase(message)
    if named_month:
        return named_month

    weekday_match = re.search(
        r"\b(?:next|this)?\s*(?:monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun)\b",
        lower,
    )
    if weekday_match:
        return weekday_match.group(0).strip()

    on_date_match = re.search(
        r"\bon\s+(friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b",
        lower,
    )
    if on_date_match:
        return on_date_match.group(1)

    return None


def message_mentions_time(message: str) -> bool:
    lower = message.strip().lower()
    if re.search(r"\bfrom\s+.+\s+to\s+", lower):
        return True
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lower):
        return True
    if re.search(r"\b(?:at|until|between)\s+\d", lower):
        return True
    return False


def parse_flexible_date(raw: str | None, today: date | None = None) -> date | None:
    if not raw or not raw.strip():
        return None

    today = today or date.today()
    normalized = raw.strip().lower()

    if normalized == "today":
        return today
    if normalized == "tomorrow":
        return today + timedelta(days=1)

    named_month_date = _parse_named_month_date(raw, today)
    if named_month_date:
        return named_month_date

    weekday_date = _parse_weekday_phrase(raw, today)
    if weekday_date:
        return weekday_date

    slash_date = _parse_slash_date(raw)
    if slash_date:
        return slash_date

    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None
