"""Detect eCard-related messages."""

import re

from src.agents.orchestrator.parser import OCCASIONS
from src.storage.models.ecard_request import EcardRequest

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


def parse_ecard_request(text: str, *, from_slash_command: bool = False) -> dict | None:
    message = text.strip()
    if not message:
        return None

    if from_slash_command:
        req = _parse_slash_ecard(message)
        if req:
            return {
                "recipient": req.recipient,
                "occasion": req.occasion,
                "raw": message,
            }
        return None

    match = CREATE_PATTERN.search(message)
    if not match:
        if is_ecard_request(message):
            return {"recipient": None, "occasion": None, "raw": message}
        return None

    recipient = " ".join(match.group("recipient").split()).title()
    occasion = match.group("occasion")
    if occasion:
        occasion = occasion.strip().rstrip(".")
    return {"recipient": recipient, "occasion": occasion, "raw": message}


def _parse_slash_ecard(text: str) -> EcardRequest | None:
    parts = text.strip().split()
    if not parts:
        return None

    if len(parts) >= 3:
        two_word = f"{parts[-2]} {parts[-1]}".lower()
        if two_word in OCCASIONS:
            return EcardRequest(
                recipient=" ".join(parts[:-2]).title(),
                occasion=two_word,
                raw_message=text,
            )

    if len(parts) >= 2 and parts[-1].lower() in OCCASIONS:
        return EcardRequest(
            recipient=" ".join(parts[:-1]).title(),
            occasion=parts[-1].lower(),
            raw_message=text,
        )

    return EcardRequest(
        recipient=" ".join(parts).title(),
        occasion=None,
        raw_message=text,
    )
