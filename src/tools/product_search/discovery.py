"""Discovery phase — Exa MCP web search for gift inspiration."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from src.mcp.client import call_mcp_server
from src.shared.integration_settings import get_shopping_pipeline_settings, is_discovery_enabled

logger = logging.getLogger("gift_assistant.product_search.discovery")


def build_discovery_query(
    recipient: str,
    occasion: str | None,
    profile_chunks: list[str] | None = None,
    feedback: str | None = None,
) -> str:
    """Query tuned for human-curated gift list articles."""
    parts = [f"best gift ideas for {recipient}"]
    if occasion:
        parts.append(occasion)
    if profile_chunks:
        snippet = "; ".join(profile_chunks[:3])
        parts.append(f"interests: {snippet}")
    if feedback and feedback.strip():
        parts.append(feedback.strip())
    parts.append("curated gift guide recommendations")
    return " ".join(parts)


def discover_gift_ideas(query: str) -> str:
    """Run Exa MCP web search for creative gift list inspiration."""
    if not is_discovery_enabled():
        return ""

    settings = get_shopping_pipeline_settings()
    server = settings["discovery"]
    if not server:
        return ""

    return call_mcp_server(server, query)


@tool
def exa_gift_discovery(query: str) -> str:
    """
    Discovery-phase web search for creative, human-curated gift lists and articles.
    Use for inspiration before checking live retail prices.
    """
    try:
        result = discover_gift_ideas(query)
        if not result:
            return (
                "Discovery search is disabled. Set PRODUCT_SEARCH_ENABLED=true and "
                "configure servers.exa in config/integrations.yaml."
            )
        return result
    except Exception as exc:
        logger.exception("exa_gift_discovery failed")
        return f"Discovery search failed: {exc}"
