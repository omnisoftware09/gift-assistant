from src.agents.orchestrator.parser import parse_gift_request


def test_graduation_possessive():
    req = parse_gift_request("recommend gift for Sarah's graduation")
    assert req is not None
    assert req.recipient == "Sarah"
    assert req.occasion == "graduation"


def test_gift_for_without_apostrophe():
    req = parse_gift_request("gift for Sarah graduation")
    assert req is not None
    assert req.recipient == "Sarah"
    assert req.occasion == "graduation"


def test_slash_command():
    req = parse_gift_request("Mom birthday", from_slash_command=True)
    assert req is not None
    assert req.recipient == "Mom"
    assert req.occasion == "birthday"


def test_recipient_only():
    req = parse_gift_request("gift ideas for John")
    assert req is not None
    assert req.recipient == "John"
    assert req.occasion is None


def test_non_gift_returns_none():
    assert parse_gift_request("what events do I have tomorrow") is None


def test_gift_with_pronoun_occasion_and_feedback():
    msg = "Gift for Sarah for her birthday but something in trend these days"
    req = parse_gift_request(msg)
    assert req is not None
    assert req.recipient == "Sarah"
    assert req.occasion == "birthday"
    assert "trend" in req.raw_message
