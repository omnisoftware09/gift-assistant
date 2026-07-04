from src.tools.vector_db.chunker import chunk_text


def test_two_sentences():
    text = "Sarah loves hiking. She enjoys photography. She drinks coffee daily."
    chunks = chunk_text(text)
    assert len(chunks) == 2
    assert "hiking" in chunks[0]
    assert "coffee" in chunks[1]


def test_single_blob():
    chunks = chunk_text("hiking coffee photography")
    assert len(chunks) == 1


def test_profile_parser():
    from src.agents.subagents.profile_collector.parser import parse_profile_save

    result = parse_profile_save("Sarah likes hiking and coffee")
    assert result == ("Sarah", "hiking and coffee")
