"""Product search tools — discovery + retail verification."""

from src.tools.product_search.discovery import build_discovery_query, discover_gift_ideas, exa_gift_discovery
from src.tools.product_search.retail import (
    amazon_rainforest_verify,
    build_retail_query,
    google_shopping_verify,
    verify_gift_retail,
)

# Backward-compatible aliases used by the gift graph
build_product_search_query = build_discovery_query
search_web_products = discover_gift_ideas

from src.tools.product_search.discovery import exa_gift_discovery as web_product_search  # noqa: E402

PRODUCT_SEARCH_TOOLS = [
    exa_gift_discovery,
    google_shopping_verify,
    amazon_rainforest_verify,
]

__all__ = [
    "PRODUCT_SEARCH_TOOLS",
    "amazon_rainforest_verify",
    "build_discovery_query",
    "build_product_search_query",
    "build_retail_query",
    "discover_gift_ideas",
    "exa_gift_discovery",
    "google_shopping_verify",
    "search_web_products",
    "verify_gift_retail",
    "web_product_search",
]
