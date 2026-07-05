"""Prompts for eCard Generator."""

ECARD_PICK_FOOTER = (
    "\n\n_Reply *1*, *2*, or *3* to choose a design · *done* to cancel_"
)

ECARD_REFINE_FOOTER = (
    "\n\n_Describe changes for this design (e.g. *add a cartoon girl with grad cap*) · "
    "*finalize* when ready to download · *done* to cancel · "
    "*pick 2* to switch designs_"
)

# Legacy alias
ECARD_REFINEMENT_FOOTER = ECARD_PICK_FOOTER


def draft_ecard_prompt(
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str],
    *,
    age_range: str | None = None,
    past_gifts_summary: str = "",
    past_ecards_summary: str = "",
    feedback: str | None = None,
    iteration: int = 1,
) -> str:
    profile = "\n".join(f"- {c}" for c in profile_chunks) if profile_chunks else "No profile on file."
    occasion_line = occasion or "a special occasion"
    age_line = age_range or "not specified"
    feedback_block = ""
    if feedback:
        feedback_block = f"\nUser feedback to incorporate:\n{feedback}\n"

    return f"""You are a greeting card writer for Gift Assistant.

Recipient: {recipient}
Age range: {age_line}
Occasion: {occasion_line}
Round: {iteration}

Known interests / profile:
{profile}

Past gifts (for tone/context, do not mention explicitly unless natural):
{past_gifts_summary or "None recorded."}

Past eCards sent (avoid repeating the same message or style):
{past_ecards_summary or "None recorded."}
{feedback_block}
Write exactly 3 different eCard options with distinct styles:
1. heartfelt — warm and sincere
2. funny — light humor, still appropriate
3. formal — polished and professional

Return ONLY a JSON array (no markdown) of objects with keys:
- "style": one of "heartfelt", "funny", "formal"
- "headline": short card title (5-8 words)
- "message": 2-4 sentences, personal and specific to the recipient
- "sign_off": closing line e.g. "With love," or "Best wishes,"

Example:
[{{"style":"heartfelt","headline":"Happy Birthday, Sarah!","message":"...","sign_off":"With love,"}}]
"""


def refine_ecard_prompt(
    card: dict,
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str],
    *,
    feedback: str,
    prior_feedback: list[str] | None = None,
) -> str:
    profile = "\n".join(f"- {c}" for c in profile_chunks) if profile_chunks else "No profile on file."
    history = "\n".join(f"- {f}" for f in (prior_feedback or []))
    history_block = f"\nPrevious refinement requests:\n{history}\n" if history else ""

    return f"""You are refining ONE greeting card for Gift Assistant.

Recipient: {recipient}
Occasion: {occasion or "a special occasion"}
Style (keep this): {card.get("style", "heartfelt")}

Current card:
- headline: {card.get("headline", "")}
- message: {card.get("message", "")}
- sign_off: {card.get("sign_off", "")}

Profile context:
{profile}
{history_block}
Latest user feedback (apply to text AND consider for visual theme):
{feedback}

Update ONLY the wording if needed. Keep the same style ({card.get("style")}).
Return ONLY a JSON object (not array) with keys:
- "style": "{card.get("style", "heartfelt")}"
- "headline": updated headline
- "message": updated message
- "sign_off": updated sign_off
"""
