from datetime import datetime, timedelta, timezone

from src.agents.subagents.event_monitor.event_parser import parse_event_for_gift
from src.storage.models.calendar_event import CalendarEvent
from src.shared.notification_store import NotificationStore


def _event(summary: str, days_from_now: int = 3) -> CalendarEvent:
    start = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return CalendarEvent(id="evt1", summary=summary, start=start, all_day=True)


def test_parse_sarahs_birthday():
    gift = parse_event_for_gift(_event("Sarah's birthday"))
    assert gift is not None
    assert gift.recipient == "Sarah"
    assert gift.occasion == "birthday"


def test_parse_mom_graduation():
    gift = parse_event_for_gift(_event("Sarah graduation"))
    assert gift is not None
    assert gift.recipient == "Sarah"
    assert gift.occasion == "graduation"


def test_non_gift_event():
    assert parse_event_for_gift(_event("Team standup")) is None


def test_notification_store(tmp_path):
    store = NotificationStore(tmp_path / "notified.json")
    assert store.should_notify("evt1") is True
    store.mark_notified("evt1")
    assert store.should_notify("evt1") is False
    store.mark_snoozed("evt2", days=1)
    assert store.should_notify("evt2") is False
    store.mark_skipped("evt3")
    assert store.should_notify("evt3") is False
