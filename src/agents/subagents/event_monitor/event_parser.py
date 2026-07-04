"""Extract gift recipient/occasion from calendar event titles."""

import re

from src.storage.models.calendar_event import CalendarEvent
from src.storage.models.gift_request import GiftRequest

GIFT_OCCASION = re.compile(
    r"\b(birthday|anniversary|graduation|wedding|baby shower|retirement|"
    r"housewarming|promotion|christmas)\b",
    re.IGNORECASE,
)

POSSESSIVE = re.compile(
    r"(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)'s\s+(?P<occasion>[A-Za-z\s]+)",
    re.IGNORECASE,
)


def is_gift_relevant_event(event: CalendarEvent) -> bool:
    return parse_event_for_gift(event) is not None


def parse_event_for_gift(event: CalendarEvent) -> GiftRequest | None:
    summary = event.summary.strip()
    if not GIFT_OCCASION.search(summary):
        return None

    possessive = POSSESSIVE.search(summary)
    if possessive:
        occasion = _clean_occasion(possessive.group("occasion"))
        return GiftRequest(
            recipient=_clean_name(possessive.group("recipient")),
            occasion=occasion,
            raw_message=summary,
        )

    # "Mom birthday" or "Sarah graduation"
    loose = re.match(
        r"^(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)\s*'?s?\s+(?P<occasion>.+)$",
        summary,
        re.IGNORECASE,
    )
    if loose:
        occasion = _clean_occasion(loose.group("occasion"))
        if occasion and GIFT_OCCASION.search(occasion):
            return GiftRequest(
                recipient=_clean_name(loose.group("recipient")),
                occasion=occasion,
                raw_message=summary,
            )

    # Standalone occasion e.g. "Birthday party" → recipient "Friend"
    occasion_only = GIFT_OCCASION.search(summary)
    if occasion_only:
        return GiftRequest(
            recipient="Friend",
            occasion=occasion_only.group(1).lower(),
            raw_message=summary,
        )

    return None


def _clean_name(name: str) -> str:
    return " ".join(name.strip().split()).title()


def _clean_occasion(occasion: str) -> str:
    text = " ".join(occasion.strip().split()).lower()
    match = GIFT_OCCASION.search(text)
    return match.group(1).lower() if match else text
