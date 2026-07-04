from datetime import datetime, timedelta

from src.storage.models.calendar_event import CalendarEvent
from src.langchain_core.observability import trace_tool
from src.tools.calendar.client import CalendarNotConnectedError, get_calendar_service


@trace_tool("calendar.fetch_events_between")
def fetch_events_between(start: datetime, end: datetime) -> list[CalendarEvent]:
    service = get_calendar_service()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start_raw = item["start"].get("dateTime", item["start"].get("date"))
        all_day = "T" not in start_raw
        if all_day:
            dt = datetime.fromisoformat(start_raw)
            dt = dt.replace(tzinfo=start.tzinfo)
        else:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        events.append(
            CalendarEvent(
                id=item["id"],
                summary=item.get("summary", "(No title)"),
                start=dt,
                all_day=all_day,
            )
        )
    return events


def fetch_events_for_day(day_offset: int = 0) -> list[CalendarEvent]:
    now = datetime.now().astimezone()
    start = (now + timedelta(days=day_offset)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=1)
    return fetch_events_between(start, end)


def fetch_upcoming_events(days: int = 7) -> list[CalendarEvent]:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)
    return fetch_events_between(start, end)
