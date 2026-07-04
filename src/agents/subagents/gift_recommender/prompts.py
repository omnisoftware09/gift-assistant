"""Prompts for Gift Recommender LangGraph nodes."""


def profile_block(chunks: list[str]) -> str:
    if not chunks:
        return "No profile on file — use general, thoughtful gift ideas for the occasion."
    return "\n".join(f"- {c}" for c in chunks)


def past_gifts_block(past_gifts_summary: str, excluded_categories: list[str]) -> str:
    if not past_gifts_summary or past_gifts_summary == "No past gifts recorded.":
        return "No past gifts on record."
    cats = ", ".join(excluded_categories) if excluded_categories else "none listed"
    return f"""Past gifts (DO NOT repeat same or very similar items/categories):
{past_gifts_summary}

Excluded categories (avoid these and close variants): {cats}
"""


def feedback_block(feedback: str | None) -> str:
    if not feedback or not feedback.strip():
        return ""
    return f"""
User feedback from previous round (incorporate in new ideas):
{feedback}
"""


def search_prompt(
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str],
    *,
    age_range: str | None = None,
    past_gifts_summary: str = "",
    excluded_categories: list[str] | None = None,
    feedback: str | None = None,
) -> str:
    occasion_line = occasion or "a general gift occasion"
    age_line = age_range or "not specified"
    excluded = excluded_categories or []
    return f"""You are a gift idea researcher.

Recipient: {recipient}
Age range: {age_line}
Occasion: {occasion_line}

Known interests / profile:
{profile_block(profile_chunks)}

{past_gifts_block(past_gifts_summary, excluded)}
{feedback_block(feedback)}
RULES:
- Do NOT recommend gifts in the same category as past gifts listed above.
- Do NOT recommend gifts very similar in type to past gifts (e.g. another daypack if they got a backpack).
- If user feedback is provided, adjust ideas to match it.
- Prefer ideas that match the profile when available.

Propose exactly 5 NEW concrete gift ideas.

Return ONLY a JSON array (no markdown fences) of objects with keys:
- "title": short gift name
- "description": 1-2 sentences
- "price_range": e.g. "$20-40", "$50-100", "$100+"
- "category": e.g. "experience", "home", "tech", "food", "fashion", "outdoors"

Example:
[{{"title":"Trail daypack","description":"...","price_range":"$40-70","category":"outdoors"}}]
"""


def evaluate_prompt(
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str],
    candidates: list[dict],
    *,
    age_range: str | None = None,
    past_gifts_summary: str = "",
    excluded_categories: list[str] | None = None,
    feedback: str | None = None,
) -> str:
    occasion_line = occasion or "a general gift occasion"
    age_line = age_range or "not specified"
    excluded = excluded_categories or []
    return f"""You are a gift evaluator.

Recipient: {recipient}
Age range: {age_line}
Occasion: {occasion_line}

Known interests / profile:
{profile_block(profile_chunks)}

{past_gifts_block(past_gifts_summary, excluded)}
{feedback_block(feedback)}
RULES when scoring:
- Penalize heavily (rating below 40) if gift matches an excluded category or is very similar to a past gift.
- Boost rating if gift aligns with user feedback.
- Score 0-100 for overall fit for this person and occasion.

Candidates (JSON):
{candidates}

Return ONLY a JSON array (no markdown fences) of objects with keys:
- "title": must match a candidate title
- "rating": number 0-100 (LLM quality/fit rating)
- "reason": one short sentence explaining the rating

Include every candidate exactly once.
"""


GIFT_REFINEMENT_FOOTER = (
    "\n\n_Reply *1*, *2*, or *3* to select · share feedback to refine · *done* to finish without selecting_"
)
