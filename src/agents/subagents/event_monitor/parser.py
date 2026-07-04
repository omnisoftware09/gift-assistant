"""Parse calendar / event queries from Slack messages."""

import re
from dataclasses import dataclass

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

EVENT_TRIGGER = re.compile(
    r"\b(event|events|calendar|schedule|upcoming|birthday|anniversary)\b",
    re.IGNORECASE,
)


@dataclass
class EventQuery:
    mode: str  # "day" | "upcoming"
    day_offset: int = 0
    days_ahead: int = 7
    label: str = "today"


def is_event_query(text: str) -> bool:
    return bool(EVENT_TRIGGER.search(text))


def parse_event_query(text: str) -> EventQuery:
    lower = text.lower().strip()

    if re.search(r"\btomorrow\b", lower):
        return EventQuery(mode="day", day_offset=1, label="tomorrow")
    if re.search(r"\byesterday\b", lower):
        return EventQuery(mode="day", day_offset=-1, label="yesterday")
    if re.search(r"\btoday\b", lower):
        return EventQuery(mode="day", day_offset=0, label="today")

    if re.search(r"\b(this week|upcoming|next few days)\b", lower):
        return EventQuery(mode="upcoming", days_ahead=7, label="the next 7 days")

    now_label = _weekday_offset(lower)
    if now_label is not None:
        offset, name = now_label
        return EventQuery(mode="day", day_offset=offset, label=name)

    # Default for /events or generic "show events"
    return EventQuery(mode="upcoming", days_ahead=7, label="the next 7 days")


def _weekday_offset(lower: str) -> tuple[int, str] | None:
    from datetime import datetime

    now = datetime.now().astimezone()
    for index, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{re.escape(name)}\b", lower):
            offset = (index - now.weekday()) % 7
            return offset, name.capitalize()
    return None
