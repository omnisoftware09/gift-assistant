from src.agents.subagents.ecard_generator.parser import is_ecard_request, parse_ecard_request


def test_ecard_detection():
    assert is_ecard_request("create a greeting card for Mom")
    assert not is_ecard_request("recommend gift for Mom")


def test_ecard_parse():
    parsed = parse_ecard_request("send an ecard for Sarah for her graduation")
    assert parsed is not None
    assert parsed["recipient"] == "Sarah"
    assert parsed["occasion"] == "her graduation"
