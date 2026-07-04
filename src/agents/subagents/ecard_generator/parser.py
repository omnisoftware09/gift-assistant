"""Detect eCard-related messages."""

import re

ECARD_TRIGGER = re.compile(
    r"\b(ecard|e-card|greeting card|birthday card|thank you card|send a card)\b",
    re.IGNORECASE,
)

CREATE_PATTERN = re.compile(
    r"(?:create|make|send|write)\s+(?:an?\s+)?(?:ecard|e-card|greeting card|card)\s+"
    r"(?:for\s+)?(?P<recipient>[A-Za-z]+)"
    r"(?:\s+for\s+(?P<occasion>.+))?",
    re.IGNORECASE,
)


def is_ecard_request(text: str) -> bool:
    return bool(ECARD_TRIGGER.search(text))


def parse_ecard_request(text: str) -> dict | None:
    match = CREATE_PATTERN.search(text.strip())
    if not match:
        if is_ecard_request(text):
            return {"recipient": None, "occasion": None, "raw": text.strip()}
        return None

    recipient = " ".join(match.group("recipient").split()).title()
    occasion = match.group("occasion")
    if occasion:
        occasion = occasion.strip().rstrip(".")
    return {"recipient": recipient, "occasion": occasion, "raw": text.strip()}
