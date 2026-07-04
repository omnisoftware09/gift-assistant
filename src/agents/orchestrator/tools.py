"""Orchestrator LangChain tools — recipient context and gift history (SQLite)."""

import json

from langchain_core.tools import tool

from src.storage.gift_history.store import get_gift_history_store


@tool
def get_recipient_gift_context(recipient: str) -> str:
    """
    Load a recipient's short profile and past gift history from SQLite.
    Use before starting or refining gift recommendations.
    Returns name, age_range, past gifts, and categories to avoid repeating.
    """
    ctx = get_gift_history_store().get_recipient_context(recipient)
    payload = {
        "name": ctx.name,
        "age_range": ctx.age_range,
        "past_gifts": [
            {
                "title": g.title,
                "category": g.category,
                "occasion": g.occasion,
                "selected_at": g.selected_at,
            }
            for g in ctx.past_gifts
        ],
        "excluded_categories": ctx.excluded_categories(),
        "rule": "Do not recommend gifts in the same or very similar category as past gifts.",
    }
    return json.dumps(payload, indent=2)


@tool
def save_selected_gift(
    recipient: str,
    title: str,
    category: str,
    occasion: str = "",
    description: str = "",
) -> str:
    """
    Record a gift the user selected for a recipient in SQLite gift history.
    Call when the user picks option 1, 2, or 3 from recommendations.
    """
    store = get_gift_history_store()
    gift_id = store.save_selected_gift(
        recipient,
        title,
        category,
        occasion=occasion or None,
        description=description or None,
    )
    return f"Saved gift #{gift_id} for {recipient.strip().title()}: {title} [{category}]"


@tool
def set_recipient_age_range(recipient: str, age_range: str) -> str:
    """
    Set or update a recipient's age range (e.g. '30-35', '40-45') in SQLite.
    """
    get_gift_history_store().set_age_range(recipient, age_range)
    return f"Set age range for {recipient.strip().title()} to {age_range}"


ORCHESTRATOR_GIFT_TOOLS = [
    get_recipient_gift_context,
    save_selected_gift,
    set_recipient_age_range,
]


def load_recipient_context(recipient: str):
    """Direct call for orchestrator (no ReAct loop required)."""
    from src.storage.models.recipient_context import RecipientContext

    return get_gift_history_store().get_recipient_context(recipient)


def record_selected_gift(
    recipient: str,
    title: str,
    category: str,
    occasion: str | None = None,
    description: str | None = None,
) -> int:
    """Direct call when user selects a gift option."""
    return get_gift_history_store().save_selected_gift(
        recipient, title, category, occasion=occasion, description=description
    )
