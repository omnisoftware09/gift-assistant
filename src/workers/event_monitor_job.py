"""Send proactive Slack alerts for approaching gift-relevant calendar events."""

import os

from slack_sdk import WebClient

from src.agents.subagents.event_monitor.event_parser import (
    is_gift_relevant_event,
    parse_event_for_gift,
)
from src.interfaces.slack.formatters.alert_blocks import build_proactive_alert
from src.langchain_core.observability import trace_agent
from src.shared.notification_store import NotificationStore
from src.tools.calendar.client import CalendarNotConnectedError
from src.tools.calendar.read_events import fetch_upcoming_events


@trace_agent("proactive_worker", run_type="tool")
def run_proactive_check(client: WebClient, user_id: str | None = None) -> dict:
    """
    Check calendar for approaching events and DM the user.
    Returns dict with sent count and diagnostic info for Slack.
    """
    user_id = user_id or os.getenv("SLACK_ALERT_USER_ID")
    if not user_id:
        return {
            "sent": 0,
            "message": "SLACK_ALERT_USER_ID not set in .env",
        }

    alert_days = int(os.getenv("PROACTIVE_ALERT_DAYS", "7"))
    store = NotificationStore()

    try:
        events = fetch_upcoming_events(days=alert_days)
    except CalendarNotConnectedError as exc:
        return {"sent": 0, "message": str(exc)}
    except Exception as exc:
        return {"sent": 0, "message": f"Calendar error: {exc}"}

    channel_id = _open_dm_channel(client, user_id)
    sent = 0
    skipped = {"out_of_range": 0, "not_gift": 0, "already_sent": 0, "unparsed": 0}
    gift_events = []

    for event in events:
        if event.days_until() < 0 or event.days_until() > alert_days:
            skipped["out_of_range"] += 1
            continue
        if not is_gift_relevant_event(event):
            skipped["not_gift"] += 1
            continue

        gift = parse_event_for_gift(event)
        if gift:
            gift_events.append((event, gift))

        if not store.should_notify(event.id):
            skipped["already_sent"] += 1
            continue
        if not gift:
            skipped["unparsed"] += 1
            continue

        alert = build_proactive_alert(event, gift)
        client.chat_postMessage(channel=channel_id, **alert)
        store.mark_notified(event.id)
        sent += 1
        print(f"PROACTIVE: sent alert for {event.summary} ({event.when_label()})")

    result = {"sent": sent, "total_events": len(events), "gift_events": len(gift_events)}

    if sent == 0:
        print("PROACTIVE: no new alerts to send")
        if not events:
            result["message"] = (
                f"No calendar events in the next {alert_days} days. "
                "Add an event like *Sarah's birthday* in Google Calendar."
            )
        elif gift_events and skipped["already_sent"]:
            names = ", ".join(f"*{e.summary}*" for e, _ in gift_events)
            result["message"] = (
                f"Alerts already sent for: {names}. "
                "Delete `data/notified_events.json` and run `/check-alerts` again to retest."
            )
        elif skipped["not_gift"] == len(events):
            result["message"] = (
                f"Found {len(events)} event(s) but none are gift-related.\n"
                "Rename or add an event with a title like:\n"
                "• *Sarah's birthday*\n"
                "• *Mom graduation*\n"
                "• *John anniversary*"
            )
        else:
            result["message"] = "No new alerts to send. Check your DM with the bot."

    return result


def _open_dm_channel(client: WebClient, user_id: str) -> str:
    response = client.conversations_open(users=user_id)
    return response["channel"]["id"]
