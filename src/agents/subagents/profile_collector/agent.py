"""Profile Collector — LangChain ReAct agent with ChromaDB tools."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.subagents.profile_collector.import_handler import (
    handle_profile_import,
    is_profile_import_command,
)
from src.agents.subagents.profile_collector.parser import parse_profile_query
from src.langchain_core.llm import get_chat_model
from src.langchain_core.observability import trace_agent
from src.profile_ingestion.service import format_ingest_summary, ingest_profiles
from src.profile_ingestion.sources import slack as slack_source
from src.shared.conversation_context import AgentResponse, SlackContext
from src.tools.vector_db.profile_store import get_profile_store
from src.tools.vector_db.tools import PROFILE_TOOLS

SYSTEM_PROMPT = """You are the Profile Collector for Gift Assistant.
Your job is to save and retrieve recipient profiles (interests, hobbies, preferences).

Use tools when needed:
- save_recipient_profile: when user shares what someone likes
- get_recipient_profile: when user asks about someone's interests
- delete_old_profiles: when user wants to remove stale data

Be concise. Confirm what you saved or found."""


def _run_react_agent(message: str) -> str:
    from langgraph.prebuilt import create_react_agent

    model = get_chat_model()
    agent = create_react_agent(model, PROFILE_TOOLS)
    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        }
    )
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)


def _run_rule_based(message: str, context: SlackContext | None = None) -> str | None:
    """Fast path without LLM for simple patterns."""
    source_ref = ""
    if context and context.thread_ts:
        source_ref = context.thread_ts

    payloads = slack_source.collect_from_message(message, source_ref=source_ref)
    if payloads:
        results = ingest_profiles(payloads)
        return format_ingest_summary(results)

    query_name = parse_profile_query(message)
    if query_name:
        chunks = get_profile_store().query_profile(query_name)
        if not chunks:
            return f"No profile found for *{query_name}* yet."
        lines = "\n".join(f"• {c}" for c in chunks)
        return f"Profile for *{query_name}*:\n{lines}"

    if "delete old profile" in message.lower() or "clean up profile" in message.lower():
        count = get_profile_store().delete_old_profiles(30)
        return f"Deleted {count} old profile chunk(s)."

    return None


@trace_agent("profile_collector")
def handle_profile_message(message: str, context: SlackContext | None = None) -> AgentResponse:
    if is_profile_import_command(message):
        return handle_profile_import(context=context)

    quick = _run_rule_based(message, context)
    if quick:
        return AgentResponse(text=quick)

    try:
        reply = _run_react_agent(message)
        return AgentResponse(text=reply)
    except Exception as exc:
        return AgentResponse(
            text=(
                f"I couldn't process that profile request ({exc}).\n"
                "Try: *Sarah likes hiking and coffee*, "
                "*What does Sarah like?*, or *import profiles*"
            )
        )
