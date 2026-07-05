"""Gift Assistant orchestrator — routes Slack messages to sub-agents."""

import logging
import re

from src.agents.orchestrator.gift_flow import handle_active_gift_session, start_gift_session
from src.agents.orchestrator.parser import parse_gift_request
from src.agents.orchestrator.router import detect_intent
from src.agents.orchestrator.tools import load_recipient_context, set_recipient_age_range
from src.agents.subagents.event_monitor.agent import handle_event_query
from src.agents.subagents.event_monitor.parser import is_event_query
from src.agents.subagents.ecard_generator.flow import handle_active_ecard_session, start_ecard_session
from src.agents.subagents.ecard_generator.parser import is_ecard_request
from src.agents.subagents.profile_collector.agent import handle_profile_message
from src.agents.subagents.profile_collector.import_handler import is_profile_import_command
from src.agents.subagents.profile_collector.parser import is_profile_message
from src.interfaces.slack.formatters.responses import welcome_blocks
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext
from src.shared.ecard_session_store import get_ecard_session_store
from src.shared.gift_session_store import get_gift_session_store

logger = logging.getLogger("gift_assistant.orchestrator")

AGE_RANGE_PATTERN = re.compile(
    r"(?P<name>[A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(?:is\s+)?age(?:\s+range)?\s+"
    r"(?P<range>\d{1,2}\s*-\s*\d{1,2})",
    re.IGNORECASE,
)

GREETING_PATTERN = re.compile(r"\b(hello|hi|hey|help)\b", re.IGNORECASE)


def _same_recipient(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def _try_new_gift_for_different_recipient(
    message: str,
    session,
    context: SlackContext,
) -> AgentResponse | None:
    """Start a fresh gift flow when user asks for someone other than the session recipient."""
    new_request = parse_gift_request(message)
    if not new_request or _same_recipient(new_request.recipient, session.recipient):
        return None

    logger.info(
        "Gift session switching recipient %s -> %s for user=%s",
        session.recipient,
        new_request.recipient,
        context.user_id,
    )
    get_gift_session_store().clear(context.user_id)
    recipient_ctx = load_recipient_context(new_request.recipient)
    return start_gift_session(new_request, context, recipient_ctx)


@trace_agent("orchestrator")
def handle_message(text: str, context: SlackContext) -> AgentResponse:
    """Process a user message and return a response for Slack."""
    message = text.strip()

    if not message:
        return AgentResponse(
            text="Send me a message and I'll help with gifts and events.",
            blocks=welcome_blocks(),
        )

    # Active sessions before greeting detection ("something" contains "hi")
    session = get_gift_session_store().get(context.user_id)
    if session:
        switched = _try_new_gift_for_different_recipient(message, session, context)
        if switched:
            return switched
        return handle_active_gift_session(message, session, context)

    ecard_session = get_ecard_session_store().get(context.user_id)
    if ecard_session:
        return handle_active_ecard_session(message, ecard_session, context)

    if GREETING_PATTERN.search(message):
        return AgentResponse(
            text="Hello! I'm your Gift Assistant.",
            blocks=welcome_blocks(),
        )

    age_match = AGE_RANGE_PATTERN.search(message)
    if age_match:
        name = " ".join(age_match.group("name").split()).title()
        age_range = age_match.group("range").replace(" ", "")
        set_recipient_age_range.invoke({"recipient": name, "age_range": age_range})
        return AgentResponse(
            text=f"Set age range for *{name}* to *{age_range}*. I'll use this for gift ideas."
        )

    # eCard before gift/events — occasion words like "birthday" overlap with event triggers
    if is_ecard_request(message) or detect_intent(message) == "ecard":
        return start_ecard_session(message, context)

    gift_request = parse_gift_request(message)
    if gift_request:
        recipient_ctx = load_recipient_context(gift_request.recipient)
        logger.info(
            "Orchestrator loaded gift context via tool recipient=%s age_range=%s past_gifts=%d",
            recipient_ctx.name,
            recipient_ctx.age_range,
            len(recipient_ctx.past_gifts),
        )
        return start_gift_session(gift_request, context, recipient_ctx)

    if is_event_query(message) or detect_intent(message) == "event":
        return handle_event_query(message)

    if is_profile_import_command(message):
        return handle_profile_message(message, context)

    if is_profile_message(message) or detect_intent(message) == "profile":
        return handle_profile_message(message, context)

    intent = detect_intent(message)
    return _response_for_intent(intent, message)


@trace_agent("orchestrator.slash_command")
def handle_slash_command(
    command: str, query: str, context: SlackContext
) -> AgentResponse:
    """Handle /gift and /events slash commands."""
    if command == "gift":
        if not query:
            return AgentResponse(
                text='Usage: `/gift Sarah graduation` or `/gift Mom birthday`'
            )
        gift_request = parse_gift_request(query, from_slash_command=True)
        if gift_request:
            existing = get_gift_session_store().get(context.user_id)
            if existing:
                get_gift_session_store().clear(context.user_id)
            recipient_ctx = load_recipient_context(gift_request.recipient)
            return start_gift_session(gift_request, context, recipient_ctx)
        return AgentResponse(
            text=f'Could not parse `/gift {query}`. Try `/gift Sarah graduation`.'
        )

    if command == "events":
        query_text = query or "upcoming events"
        return handle_event_query(query_text)

    if command == "ecard":
        if not query:
            return AgentResponse(
                text='Usage: `/ecard Mom birthday` or `/ecard Sarah graduation`'
            )
        from src.agents.subagents.ecard_generator.flow import start_ecard_session

        fake_message = f"create a greeting card for {query}"
        return start_ecard_session(fake_message, context)

    return AgentResponse(text=f"Unknown command: /{command}")


def _response_for_intent(intent: str | None, message: str) -> AgentResponse:
    if intent == "gift":
        return AgentResponse(
            text=(
                "Tell me who the gift is for, e.g. "
                '*recommend gift for Sarah\'s graduation* or `/gift Sarah graduation`'
            )
        )

    if intent == "event":
        return handle_event_query(message)

    if intent == "profile":
        return handle_profile_message(message)

    if intent == "ecard":
        return AgentResponse(
            text=(
                "Create an eCard, e.g.\n"
                "*create a greeting card for Mom for her birthday*"
            )
        )

    return AgentResponse(
        text=(
            "I'm your Gift Assistant. Ask me about gifts, events, profiles, or eCards.\n"
            "Try: *recommend gift for Sarah's graduation*"
        )
    )
