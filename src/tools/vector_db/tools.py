"""LangChain tools for Profile Collector ReAct agent."""

from langchain_core.tools import tool

from src.profile_ingestion.models import ProfilePayload
from src.profile_ingestion.service import ingest_profile
from src.tools.vector_db.profile_store import get_profile_store


@tool
def save_recipient_profile(recipient: str, interests: str) -> str:
    """
    Save or update a recipient's interests and preferences in the vector database.
    Use when the user tells you what someone likes, enjoys, or is interested in.
    interests should be 1-2 sentences describing hobbies, tastes, etc.
    """
    result = ingest_profile(
        ProfilePayload(
            recipient=recipient,
            interests_text=interests,
            source="slack",
        )
    )
    if result.chunks_saved == 0:
        return f"No profile data saved for {recipient}."
    return f"Saved {result.chunks_saved} profile chunk(s) for {recipient}."


@tool
def get_recipient_profile(recipient: str) -> str:
    """
    Look up stored interests and preferences for a recipient.
    Use before recommending gifts or when the user asks about someone's profile.
    """
    chunks = get_profile_store().query_profile(recipient)
    if not chunks:
        return f"No profile found for {recipient}."
    return f"Profile for {recipient}:\n" + "\n".join(f"• {c}" for c in chunks)


@tool
def delete_old_profiles(days_old: int = 30) -> str:
    """
    Delete profile chunks older than days_old days.
    Use when the user asks to clean up or remove stale profile data.
    """
    count = get_profile_store().delete_old_profiles(days_old)
    return f"Deleted {count} old profile chunk(s) older than {days_old} days."


PROFILE_TOOLS = [save_recipient_profile, get_recipient_profile, delete_old_profiles]
