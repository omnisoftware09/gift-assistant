"""Gift Recommender sub-agent — LangGraph search / evaluate / rank."""

import logging

from src.agents.subagents.gift_recommender.graph import run_gift_pipeline
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse
from src.storage.models.gift_request import GiftRequest
from src.tools.vector_db.profile_store import get_profile_store

logger = logging.getLogger("gift_assistant.gift_recommender")


def _gift_profile_query(recipient: str, occasion: str | None) -> str:
    query = f"gift interests and preferences for {recipient}"
    if occasion:
        query += f" {occasion}"
    return query


@trace_agent("gift_recommender")
def handle_gift_request(request: GiftRequest) -> AgentResponse:
    label = request.summary()
    occasion_line = f" for *{request.occasion}*" if request.occasion else ""

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
    profile_text = (
        "\n".join(f"• {c}" for c in profile_chunks)
        if profile_chunks
        else "_No profile saved yet — ideas are more general. Tell me what they like!_"
    )

    pipeline = run_gift_pipeline(request, profile_chunks)
    ranked = pipeline.get("ranked") or []

    if not ranked:
        return AgentResponse(
            text=(
                f"I couldn't generate gift ideas for *{request.recipient}* right now.\n"
                f"_{pipeline.get('error') or pipeline.get('status')}_"
            )
        )

    ideas_md = _format_ideas_markdown(ranked)
    text = (
        f"Gift ideas for *{request.recipient}*{occasion_line}\n\n"
        f"*Known interests:*\n{profile_text}\n\n"
        f"*Top recommendations:*\n{ideas_md}"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Gift ideas for {label}"},
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
            "text": {"type": "mrkdwn", "text": f"*Profile:*\n{profile_text}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Top recommendations:*\n{ideas_md}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Pipeline: search → evaluate → rank · {pipeline.get('status', '')}",
                }
            ],
        },
    ]

    return AgentResponse(text=text, blocks=blocks)


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
