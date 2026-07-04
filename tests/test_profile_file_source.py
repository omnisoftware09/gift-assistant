from pathlib import Path

from src.agents.subagents.profile_collector.import_handler import is_profile_import_command
from src.profile_ingestion.sources import file as file_source


def test_named_text_file():
    payloads = file_source.parse_file_content(
        "Loves hiking and coffee.",
        "sarah.txt",
        source="file",
        source_ref="sarah.txt",
    )
    assert len(payloads) == 1
    assert payloads[0].recipient == "Sarah"
    assert "hiking" in payloads[0].interests_text


def test_named_file_pronoun_lines_use_filename():
    """sarah.txt must not create a recipient named 'She'."""
    content = (
        "Sarah loves hiking and trail photography.\n"
        "She enjoys specialty coffee and reading science fiction."
    )
    payloads = file_source.parse_file_content(content, "sarah.txt")
    assert len(payloads) == 1
    assert payloads[0].recipient == "Sarah"
    assert "She enjoys" in payloads[0].interests_text
    assert "She" not in {p.recipient for p in payloads}


def test_line_per_profile_text():
    content = "Sarah likes hiking\nMom loves gardening"
    payloads = file_source.parse_file_content(content, "batch.txt")
    assert len(payloads) == 2
    assert payloads[0].recipient == "Sarah"
    assert payloads[1].recipient == "Mom"


def test_batch_file_pronoun_attaches_to_prior_recipient():
    content = "Sarah likes hiking\nShe enjoys coffee\nMom loves gardening"
    payloads = file_source.parse_file_content(content, "profiles.txt")
    assert [p.recipient for p in payloads] == ["Sarah", "Sarah", "Mom"]
    assert payloads[1].interests_text == "coffee"


def test_json_array():
    content = """[
      {"recipient": "Alex", "interests": "board games and jazz"},
      {"name": "Jordan", "text": "cycling and photography"}
    ]"""
    payloads = file_source.parse_file_content(content, "profiles.json")
    assert len(payloads) == 2
    assert payloads[0].recipient == "Alex"
    assert payloads[1].recipient == "Jordan"


def test_readme_is_skipped():
    payloads = file_source.parse_file_content(
        "# Profile import inbox\nDrop files here.",
        "README.md",
    )
    assert payloads == []


def test_collect_from_inbox_samples():
    inbox = Path("data/profile_imports/inbox")
    if not inbox.exists():
        return
    payloads = file_source.collect_from_path(inbox)
    recipients = {p.recipient for p in payloads}
    assert "Sarah" in recipients
    assert "Mom" in recipients
    assert "Alex" in recipients
    assert "Readme" not in recipients


def test_import_command_detection():
    assert is_profile_import_command("import profiles")
    assert is_profile_import_command("please import profile from inbox")
    assert not is_profile_import_command("Sarah likes tea")
