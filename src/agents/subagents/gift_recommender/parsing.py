"""Parse LLM JSON responses for gift ideas."""

import json
import re
from typing import Any


def extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from model output (tolerates markdown fences)."""
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


def normalize_candidates(raw: list[dict]) -> list[dict]:
    ideas: list[dict] = []
    for item in raw:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        ideas.append(
            {
                "title": title,
                "description": str(item.get("description") or "").strip(),
                "price_range": str(item.get("price_range") or "varies").strip(),
                "category": str(item.get("category") or "general").strip(),
            }
        )
    return ideas


def apply_ratings(candidates: list[dict], scored: list[dict]) -> list[dict]:
    """Merge LLM ratings into candidates; default rating 50 if missing."""
    by_title = {
        str(item.get("title") or "").strip().lower(): item for item in scored
    }
    evaluated: list[dict] = []
    for candidate in candidates:
        key = candidate["title"].lower()
        match = by_title.get(key, {})
        raw = match.get("rating", match.get("score", 50))
        try:
            rating_val = float(raw)
        except (TypeError, ValueError):
            rating_val = 50.0
        rating_val = max(0.0, min(100.0, rating_val))
        evaluated.append(
            {
                **candidate,
                "rating": rating_val,
                "reason": str(match.get("reason") or "Fits the occasion.").strip(),
            }
        )
    return evaluated


def apply_scores(candidates: list[dict], scored: list[dict]) -> list[dict]:
    """Backward-compatible alias — returns ideas with rating field."""
    return apply_ratings(candidates, scored)


def rank_ideas(evaluated: list[dict], top_n: int = 3) -> list[dict]:
    """Deprecated: use rank_ideas_weighted from scoring.py."""
    from src.agents.subagents.gift_recommender.scoring import rank_ideas_weighted

    return rank_ideas_weighted(evaluated, top_n=top_n)


def fallback_candidates(recipient: str, occasion: str | None) -> list[dict]:
    """Used when the LLM returns nothing usable."""
    label = occasion or "celebration"
    return [
        {
            "title": f"Personalized keepsake for {recipient}",
            "description": f"A custom photo frame or engraved item for their {label}.",
            "price_range": "$25-50",
            "category": "keepsake",
        },
        {
            "title": "Experience gift card",
            "description": f"A voucher for a class, outing, or meal related to their interests.",
            "price_range": "$40-100",
            "category": "experience",
        },
        {
            "title": "Curated care package",
            "description": "A small box of snacks, notes, and themed items for the occasion.",
            "price_range": "$30-60",
            "category": "food",
        },
        {
            "title": "Quality everyday upgrade",
            "description": "A nicer version of something they use often (mug, journal, headphones).",
            "price_range": "$20-80",
            "category": "home",
        },
        {
            "title": "Charitable donation in their name",
            "description": f"Donate to a cause they care about and share a card for the {label}.",
            "price_range": "$25-100",
            "category": "charity",
        },
    ]
