"""Detect profile-related messages."""

import re

PROFILE_TRIGGER = re.compile(
    r"\b(profile|likes|loves|enjoys|interested in|prefers|into|hobby|hobbies)\b",
    re.IGNORECASE,
)

SAVE_PATTERN = re.compile(
    r"(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)\s+"
    r"(?:likes|loves|enjoys|is into|is interested in|prefers)\s+"
    r"(?P<interests>.+)",
    re.IGNORECASE,
)

ASK_PATTERN = re.compile(
    r"(?:what|show|tell me)\s+(?:does\s+)?(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)"
    r"\s+(?:like|love|enjoy|prefer)",
    re.IGNORECASE,
)


def is_profile_message(text: str) -> bool:
    return bool(PROFILE_TRIGGER.search(text))


def parse_profile_save(text: str) -> tuple[str, str] | None:
    match = SAVE_PATTERN.search(text.strip())
    if not match:
        return None
    recipient = " ".join(match.group("recipient").split()).title()
    interests = match.group("interests").strip().rstrip(".")
    return recipient, interests


def parse_profile_query(text: str) -> str | None:
    match = ASK_PATTERN.search(text.strip())
    if match:
        return " ".join(match.group("recipient").split()).title()
    return None
