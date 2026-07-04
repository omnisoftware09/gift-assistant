"""Collect profiles from Slack messages."""

from src.agents.subagents.profile_collector.parser import parse_profile_save
from src.profile_ingestion.models import ProfilePayload


def collect_from_message(message: str, source_ref: str = "") -> list[ProfilePayload]:
    """Parse a Slack message into profile payloads."""
    parsed = parse_profile_save(message)
    if not parsed:
        return []

    recipient, interests = parsed
    return [
        ProfilePayload(
            recipient=recipient,
            interests_text=interests,
            source="slack",
            source_ref=source_ref,
        )
    ]
