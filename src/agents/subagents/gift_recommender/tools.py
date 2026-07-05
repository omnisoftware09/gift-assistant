"""LangChain tools for Gift Recommender (MCP web search)."""

from src.tools.product_search.web_search import PRODUCT_SEARCH_TOOLS

GIFT_SEARCH_TOOLS = list(PRODUCT_SEARCH_TOOLS)
