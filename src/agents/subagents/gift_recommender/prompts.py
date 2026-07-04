"""Prompts for Gift Recommender LangGraph nodes."""


def profile_block(chunks: list[str]) -> str:
    if not chunks:
        return "No profile on file — use general, thoughtful gift ideas for the occasion."
    return "\n".join(f"- {c}" for c in chunks)


def search_prompt(recipient: str, occasion: str | None, profile_chunks: list[str]) -> str:
    occasion_line = occasion or "a general gift occasion"
    return f"""You are a gift idea researcher.

Recipient: {recipient}
Occasion: {occasion_line}

Known interests / profile:
{profile_block(profile_chunks)}

Propose exactly 5 concrete gift ideas. Prefer ideas that match the profile when available.

Return ONLY a JSON array (no markdown fences) of objects with keys:
- "title": short gift name
- "description": 1-2 sentences
- "price_range": e.g. "$20-40", "$50-100", "$100+"
- "category": e.g. "experience", "home", "tech", "food", "fashion"

Example:
[{{"title":"Trail daypack","description":"...","price_range":"$40-70","category":"outdoors"}}]
"""


def evaluate_prompt(
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str],
    candidates: list[dict],
) -> str:
    occasion_line = occasion or "a general gift occasion"
    return f"""You are a gift evaluator.

Recipient: {recipient}
Occasion: {occasion_line}

Known interests / profile:
{profile_block(profile_chunks)}

Candidates (JSON):
{candidates}

Score each candidate from 0 to 100 for how well it fits this person and occasion.
Higher ratings for strong profile match and occasion appropriateness.

Return ONLY a JSON array (no markdown fences) of objects with keys:
- "title": must match a candidate title
- "rating": number 0-100 (LLM quality/fit rating)
- "reason": one short sentence explaining the rating

Include every candidate exactly once.
"""
