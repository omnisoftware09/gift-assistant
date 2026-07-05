"""Parse LLM JSON for eCard drafts."""

import json
import re


def extract_json_array(text: str) -> list[dict]:
    if not text or not text.strip():
        return []

    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def normalize_ecard_variants(raw: list[dict]) -> list[dict]:
    styles_seen: set[str] = set()
    variants: list[dict] = []
    for item in raw:
        style = str(item.get("style") or "heartfelt").strip().lower()
        headline = str(item.get("headline") or "").strip()
        message = str(item.get("message") or "").strip()
        sign_off = str(item.get("sign_off") or "Best wishes,").strip()
        if not headline or not message:
            continue
        if style in styles_seen:
            continue
        styles_seen.add(style)
        variants.append(
            {
                "style": style,
                "headline": headline,
                "message": message,
                "sign_off": sign_off,
            }
        )
    return variants


def fallback_ecard_variants(recipient: str, occasion: str | None) -> list[dict]:
    label = occasion or "this special day"
    return [
        {
            "style": "heartfelt",
            "headline": f"Thinking of you, {recipient}",
            "message": (
                f"Wishing you a wonderful {label}. "
                f"You mean so much — hope it is filled with joy."
            ),
            "sign_off": "With love,",
        },
        {
            "style": "funny",
            "headline": f"Another trip around the sun, {recipient}!",
            "message": (
                f"Happy {label}! You're not older, you're just increasing in value."
            ),
            "sign_off": "Cheers,",
        },
        {
            "style": "formal",
            "headline": f"Warm wishes on your {label}",
            "message": (
                f"Dear {recipient}, please accept my sincere congratulations "
                f"and best wishes on this occasion."
            ),
            "sign_off": "Best regards,",
        },
    ]
