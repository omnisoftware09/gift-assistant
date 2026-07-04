"""Gift Recommender sub-agent — LangGraph search / evaluate / rank + refinement loop."""

import logging
from dataclasses import dataclass

from src.agents.subagents.gift_recommender.graph import run_gift_pipeline
from src.agents.subagents.gift_recommender.prompts import GIFT_REFINEMENT_FOOTER
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext
from src.storage.models.gift_request import GiftRequest
from src.storage.models.recipient_context import RecipientContext
from src.tools.vector_db.profile_store import get_profile_store

logger = logging.getLogger("gift_assistant.gift_recommender")


@dataclass
class GiftRecommendResult:
    response: AgentResponse
    ranked: list[dict]


def _gift_profile_query(recipient: str, occasion: str | None) -> str:
    query = f"gift interests and preferences for {recipient}"
    if occasion:
        query += f" {occasion}"
    return query


def _combined_feedback(session_feedback: list[str], new_feedback: str | None) -> str | None:
    parts = list(session_feedback)
    if new_feedback and new_feedback.strip():
        parts.append(new_feedback.strip())
    if not parts:
        return None
    return "\n".join(parts)


@trace_agent("gift_recommender")
def run_gift_recommendation(
    request: GiftRequest,
    *,
    recipient_context: RecipientContext | None = None,
    feedback: str | None = None,
    session_feedback: list[str] | None = None,
    iteration: int = 1,
) -> GiftRecommendResult:
    label = request.summary()
    occasion_line = f" for *{request.occasion}*" if request.occasion else ""
    ctx = recipient_context or RecipientContext(name=request.recipient)

    store = get_profile_store()
    query = _gift_profile_query(request.recipient, request.occasion)
    logger.info(
        "Gift request retrieving profile from Chroma recipient=%s occasion=%r query=%r",
        request.recipient,
        request.occasion,
        query,
    )
    profile_matches = store.query_profile_with_scores(
        request.recipient,
        query=query,
    )
    profile_chunks = [match.text for match in profile_matches]

    if ctx.past_gifts:
        logger.info(
            "Gift history for %s: %d past gift(s), excluded categories=%s",
            ctx.name,
            len(ctx.past_gifts),
            ctx.excluded_categories(),
        )

    combined = _combined_feedback(session_feedback or [], feedback)

    pipeline = run_gift_pipeline(
        request,
        profile_chunks,
        age_range=ctx.age_range,
        past_gifts_summary=ctx.past_gifts_summary(),
        excluded_categories=ctx.excluded_categories(),
        feedback=combined,
        iteration=iteration,
    )
    ranked = pipeline.get("ranked") or []

    profile_text = (
        "\n".join(f"• {c}" for c in profile_chunks)
        if profile_chunks
        else "_No profile saved yet — ideas are more general. Tell me what they like!_"
    )

    history_text = ctx.past_gifts_summary()
    if history_text != "No past gifts recorded.":
        profile_text += f"\n\n*Past gifts (avoid repeating):*\n{history_text}"

    if ctx.age_range:
        profile_text = f"*Age range:* {ctx.age_range}\n\n{profile_text}"

    if not ranked:
        return GiftRecommendResult(
            response=AgentResponse(
                text=(
                    f"I couldn't generate gift ideas for *{request.recipient}* right now.\n"
                    f"_{pipeline.get('error') or pipeline.get('status')}_"
                )
            ),
            ranked=[],
        )

    iter_label = f" (round {iteration})" if iteration > 1 else ""
    ideas_md = _format_ideas_markdown(ranked)
    text = (
        f"Gift ideas for *{request.recipient}*{occasion_line}{iter_label}\n\n"
        f"*Known interests:*\n{profile_text}\n\n"
        f"*Top recommendations:*\n{ideas_md}"
        f"{GIFT_REFINEMENT_FOOTER}"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Gift ideas for {label}{iter_label}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Recipient:*\n{request.recipient}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Occasion:*\n{request.occasion or '_not specified_'}",
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Profile & history:*\n{profile_text}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Top recommendations:*\n{ideas_md}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Reply *1*, *2*, or *3* to select · share feedback to refine · "
                    "*done* to finish without selecting"
                ),
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Round {iteration} · search → evaluate → rank · "
                        f"{pipeline.get('status', '')}"
                    ),
                }
            ],
        },
    ]

    return GiftRecommendResult(response=AgentResponse(text=text, blocks=blocks), ranked=ranked)


def handle_gift_request(
    request: GiftRequest,
    *,
    recipient_context: RecipientContext | None = None,
    feedback: str | None = None,
    session_feedback: list[str] | None = None,
    iteration: int = 1,
    context: SlackContext | None = None,
) -> AgentResponse:
    """Start or continue gift recommendations (session managed by orchestrator)."""
    result = run_gift_recommendation(
        request,
        recipient_context=recipient_context,
        feedback=feedback,
        session_feedback=session_feedback,
        iteration=iteration,
    )
    return result.response


def _format_ideas_markdown(ranked: list[dict]) -> str:
    lines = []
    for i, idea in enumerate(ranked, start=1):
        final = idea.get("final_score")
        closeness = idea.get("closeness")
        rating = idea.get("rating")
        score_txt = ""
        if isinstance(final, (int, float)):
            score_txt = f" · score {final:.0f}"
            if isinstance(closeness, (int, float)) and isinstance(rating, (int, float)):
                score_txt += f" (closeness {closeness:.0f}, rating {rating:.0f})"
        price = idea.get("price_range") or "varies"
        reason = idea.get("reason") or ""
        description = idea.get("description") or ""
        lines.append(
            f"*{i}. {idea['title']}* ({price}{score_txt})\n"
            f"{description}\n"
            f"_{reason}_"
        )
    return "\n\n".join(lines)
