"""Handle active gift refinement sessions (feedback / select / done)."""

import logging

from src.agents.orchestrator.gift_session import parse_gift_session_reply
from src.agents.orchestrator.tools import load_recipient_context, record_selected_gift
from src.agents.subagents.gift_recommender.agent import run_gift_recommendation
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext
from src.shared.gift_session_store import GiftSession, get_gift_session_store
from src.storage.models.gift_request import GiftRequest

logger = logging.getLogger("gift_assistant.orchestrator")


@trace_agent("orchestrator.gift_session")
def handle_active_gift_session(message: str, session: GiftSession, context: SlackContext) -> AgentResponse:
    """Process user reply while in search-evaluate-rank refinement loop."""
    action, index = parse_gift_session_reply(message)
    session_store = get_gift_session_store()

    logger.info(
        "Gift session user=%s action=%s iteration=%d recipient=%s",
        context.user_id,
        action,
        session.iteration,
        session.recipient,
    )

    if action == "done":
        session_store.clear(context.user_id)
        return AgentResponse(
            text=(
                f"Gift search for *{session.recipient}* ended.\n"
                "Start again anytime with *recommend gift for …*"
            )
        )

    if action == "select":
        if index is None or index < 0 or index >= len(session.last_ranked):
            n = len(session.last_ranked)
            return AgentResponse(
                text=f"Please pick *1*, *2*, or *3* from the list above (you have {n} options)."
            )

        gift = session.last_ranked[index]
        record_selected_gift(
            session.recipient,
            gift.get("title", "Unknown gift"),
            gift.get("category", "general"),
            occasion=session.occasion,
            description=gift.get("description"),
        )
        session_store.clear(context.user_id)
        logger.info(
            "Gift session saved selection recipient=%s gift=%r category=%s",
            session.recipient,
            gift.get("title"),
            gift.get("category"),
        )
        return AgentResponse(
            text=(
                f"Saved your choice for *{session.recipient}*:\n"
                f"*{gift.get('title')}* [{gift.get('category', 'general')}]\n\n"
                "This is stored in gift history — I won't suggest similar gifts next time."
            )
        )

    # Feedback → another search-evaluate-rank round
    request = GiftRequest(
        recipient=session.recipient,
        occasion=session.occasion,
        raw_message=message,
    )
    recipient_ctx = load_recipient_context(session.recipient)
    result = run_gift_recommendation(
        request,
        recipient_context=recipient_ctx,
        feedback=message,
        session_feedback=session.feedback,
        iteration=session.iteration + 1,
    )

    if not result.ranked:
        return result.response

    session_store.update_after_iteration(
        context.user_id,
        feedback=message,
        last_ranked=result.ranked,
    )
    logger.info(
        "Gift session refined user=%s iteration=%d feedback=%r",
        context.user_id,
        session.iteration + 1,
        message[:120],
    )
    return result.response


def start_gift_session(
    request: GiftRequest,
    context: SlackContext,
    recipient_context,
) -> AgentResponse:
    """First search-evaluate-rank round; opens refinement session."""
    result = run_gift_recommendation(
        request,
        recipient_context=recipient_context,
        iteration=1,
    )
    if result.ranked:
        get_gift_session_store().start(
            user_id=context.user_id,
            recipient=request.recipient,
            occasion=request.occasion,
            last_ranked=result.ranked,
            age_range=recipient_context.age_range,
        )
        logger.info(
            "Gift session started user=%s recipient=%s options=%d",
            context.user_id,
            request.recipient,
            len(result.ranked),
        )
    return result.response
