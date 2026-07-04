from src.agents.subagents.event_monitor.parser import parse_event_query


def test_today():
    q = parse_event_query("what events today")
    assert q.mode == "day" and q.day_offset == 0


def test_tomorrow():
    q = parse_event_query("show calendar tomorrow")
    assert q.mode == "day" and q.day_offset == 1


def test_upcoming():
    q = parse_event_query("upcoming events")
    assert q.mode == "upcoming" and q.days_ahead == 7


def test_default_events_command():
    q = parse_event_query("")
    assert q.mode == "upcoming"
