"""Product and web search tools (discovery + retail verification)."""

from src.tools.product_search.discovery import (
    build_discovery_query,
    discover_gift_ideas,
    exa_gift_discovery,
)
from src.tools.product_search.retail import (
    amazon_rainforest_verify,
    build_retail_query,
    google_shopping_verify,
    parse_retail_snapshot,
    verify_gift_retail,
)
from src.tools.product_search.web_search import PRODUCT_SEARCH_TOOLS

__all__ = [
    "PRODUCT_SEARCH_TOOLS",
    "amazon_rainforest_verify",
    "build_discovery_query",
    "build_retail_query",
    "discover_gift_ideas",
    "exa_gift_discovery",
    "google_shopping_verify",
    "parse_retail_snapshot",
    "verify_gift_retail",
]
