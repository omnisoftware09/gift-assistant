"""LangChain tools for eCard Generator ReAct agent."""

from langchain_core.tools import tool

from src.storage.gift_history.store import get_gift_history_store
from src.tools.vector_db.profile_store import get_profile_store


@tool
def get_recipient_profile_for_ecard(recipient: str) -> str:
    """
    Look up ChromaDB profile interests for a recipient before writing an eCard.
    """
    chunks = get_profile_store().query_profile(recipient)
    if not chunks:
        return f"No profile found for {recipient}."
    return f"Profile for {recipient}:\n" + "\n".join(f"• {c}" for c in chunks)


@tool
def get_recipient_ecard_history(recipient: str) -> str:
    """
    Load past eCards sent to a recipient from SQLite to avoid repeating messages.
    """
    ecards = get_gift_history_store().get_ecard_history(recipient)
    if not ecards:
        return f"No past eCards for {recipient}."
    lines = [f"• [{e.style}] {e.headline} — {e.message[:100]}" for e in ecards]
    return f"Past eCards for {recipient}:\n" + "\n".join(lines)


ECARD_TOOLS = [get_recipient_profile_for_ecard, get_recipient_ecard_history]
