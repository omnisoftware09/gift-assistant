"""Event Monitoring Agent — reads Google Calendar and returns Slack responses."""

from src.agents.subagents.event_monitor.parser import EventQuery, parse_event_query
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse
from src.tools.calendar.client import CalendarNotConnectedError
from src.tools.calendar.read_events import (
    fetch_events_for_day,
    fetch_upcoming_events,
)


@trace_agent("event_monitor")
def handle_event_query(message: str) -> AgentResponse:
    query = parse_event_query(message)

    try:
        if query.mode == "day":
            events = fetch_events_for_day(query.day_offset)
        else:
            events = fetch_upcoming_events(query.days_ahead)
    except CalendarNotConnectedError as exc:
        return AgentResponse(
            text=(
                f"{exc}\n\n"
                "Setup guide: `docs/GOOGLE_CALENDAR_SETUP.md`"
            )
        )
    except Exception:
        return AgentResponse(
            text=(
                "I couldn't read your Google Calendar. "
                "Try reconnecting: `python scripts/auth_google_calendar.py`"
            )
        )

    return _format_response(events, query)


def _format_response(events, query: EventQuery) -> AgentResponse:
    if not events:
        if query.mode == "day" and query.day_offset == 0:
            text = "No events today."
        else:
            text = f"No events for {query.label}."
        return AgentResponse(text=text)

    if query.mode == "day":
        header = (
            "Here are your events for today:"
            if query.day_offset == 0
            else f"Here are your events for {query.label}:"
        )
    else:
        header = f"Here are your events for {query.label}:"

    lines = [header, *[event.format_line() for event in events]]
    text = "\n".join(lines)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header.rstrip(":")},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(event.format_line() for event in events),
            },
        },
    ]

    return AgentResponse(text=text, blocks=blocks)
