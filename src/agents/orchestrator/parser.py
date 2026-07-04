"""Parse natural-language gift recommendation requests."""

import re

from src.storage.models.gift_request import GiftRequest

GIFT_TRIGGER = re.compile(
    r"\b("
    r"recommend|suggest|find|search|get|give|buy|"
    r"gift|gifts|present|presents|gift ideas|what to get"
    r")\b",
    re.IGNORECASE,
)

POSSESSIVE_PATTERN = re.compile(
    r"(?:\bfor\s+)?(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)'s\s+(?P<occasion>[A-Za-z]+)",
    re.IGNORECASE,
)

FOR_RECIPIENT_PATTERN = re.compile(
    r"(?:gift|present)s?\s+for\s+(?P<recipient>[A-Za-z]+)"
    r"(?:\s+(?:for|on|at)\s+(?P<occasion>[A-Za-z]+))?"
    r"\s*$",
    re.IGNORECASE,
)

RECOMMEND_FOR_PATTERN = re.compile(
    r"(?:recommend|suggest|find|search for|get)\s+(?:a\s+)?(?:gift|present)s?"
    r"\s+for\s+(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)"
    r"(?:'s\s+(?P<occasion>[A-Za-z]+))?"
    r"(?:\s+(?:for|on|at)\s+(?P<occasion2>[A-Za-z]+))?"
    r"\s*$",
    re.IGNORECASE,
)

SLASH_GIFT_PATTERN = re.compile(
    r"^(?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)"
    r"(?:\s+(?P<occasion>[A-Za-z]+))?"
    r"\s*$",
    re.IGNORECASE,
)

IDEAS_FOR_PATTERN = re.compile(
    r"gift ideas for (?P<recipient>[A-Za-z]+(?:\s+[A-Za-z]+)?)\s*$",
    re.IGNORECASE,
)

OCCASIONS = {
    "birthday",
    "graduation",
    "anniversary",
    "wedding",
    "retirement",
    "baby shower",
    "christmas",
    "thanksgiving",
    "promotion",
    "housewarming",
}


def is_gift_request(text: str) -> bool:
    return bool(GIFT_TRIGGER.search(text))


def parse_gift_request(text: str, *, from_slash_command: bool = False) -> GiftRequest | None:
    message = text.strip()
    if not message:
        return None

    if from_slash_command:
        return _parse_slash_gift(message)

    if not is_gift_request(message):
        return None

    possessive = POSSESSIVE_PATTERN.search(message)
    if possessive:
        return GiftRequest(
            recipient=_clean_name(possessive.group("recipient")),
            occasion=_clean_occasion(possessive.group("occasion")),
            raw_message=message,
        )

    recommend = RECOMMEND_FOR_PATTERN.search(message)
    if recommend:
        occasion = recommend.group("occasion") or recommend.group("occasion2")
        return GiftRequest(
            recipient=_clean_name(recommend.group("recipient")),
            occasion=_clean_occasion(occasion) if occasion else None,
            raw_message=message,
        )

    # "gift for Sarah graduation" (no apostrophe)
    loose = re.search(
        r"(?:gift|present)s?\s+for\s+(?P<recipient>[A-Za-z]+)\s+(?P<occasion>[A-Za-z]+)\s*$",
        message,
        re.IGNORECASE,
    )
    if loose:
        return GiftRequest(
            recipient=_clean_name(loose.group("recipient")),
            occasion=_clean_occasion(loose.group("occasion")),
            raw_message=message,
        )

    for_recipient = FOR_RECIPIENT_PATTERN.search(message)
    if for_recipient:
        return GiftRequest(
            recipient=_clean_name(for_recipient.group("recipient")),
            occasion=_clean_occasion(for_recipient.group("occasion"))
            if for_recipient.group("occasion")
            else None,
            raw_message=message,
        )

    ideas = IDEAS_FOR_PATTERN.search(message)
    if ideas:
        return GiftRequest(
            recipient=_clean_name(ideas.group("recipient")),
            occasion=None,
            raw_message=message,
        )

    return None


def _parse_slash_gift(text: str) -> GiftRequest | None:
    """Parse `/gift Mom birthday` or `/gift Sarah graduation`."""
    parts = text.strip().split()
    if not parts:
        return None

    # Prefer known occasion as the trailing word(s), so "Mom birthday"
    # is recipient=Mom, not recipient="Mom Birthday".
    if len(parts) >= 3:
        two_word = f"{parts[-2]} {parts[-1]}".lower()
        if two_word in OCCASIONS:
            return GiftRequest(
                recipient=_clean_name(" ".join(parts[:-2])),
                occasion=two_word,
                raw_message=text,
            )

    if len(parts) >= 2 and parts[-1].lower() in OCCASIONS:
        return GiftRequest(
            recipient=_clean_name(" ".join(parts[:-1])),
            occasion=parts[-1].lower(),
            raw_message=text,
        )

    return GiftRequest(
        recipient=_clean_name(" ".join(parts)),
        occasion=None,
        raw_message=text,
    )


def _clean_name(name: str) -> str:
    return " ".join(name.strip().split()).title()


def _clean_occasion(occasion: str | None) -> str | None:
    if not occasion:
        return None
    cleaned = " ".join(occasion.strip().split()).lower()
    return cleaned
