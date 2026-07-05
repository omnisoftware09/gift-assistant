from unittest.mock import MagicMock, patch

import pytest

from src.agents.subagents.gift_recommender.graph import search_node, verify_node
from src.agents.subagents.gift_recommender.prompts import search_prompt, web_search_block
from src.mcp.client import build_tool_arguments, extract_tool_text, resolve_env_placeholders
from src.shared.integration_settings import (
    is_discovery_enabled,
    is_product_search_enabled,
    is_verification_enabled,
    load_integrations,
)
from src.tools.product_search.discovery import build_discovery_query, exa_gift_discovery
from src.tools.product_search.retail import parse_retail_snapshot, verify_gift_retail
from src.tools.product_search.web_search import web_product_search


@pytest.fixture(autouse=True)
def clear_integration_cache():
    load_integrations.cache_clear()
    yield
    load_integrations.cache_clear()


def test_build_discovery_query_includes_profile_and_feedback():
    query = build_discovery_query(
        "Sarah",
        "graduation",
        profile_chunks=["hiking", "photography"],
        feedback="something trendy",
    )
    assert "Sarah" in query
    assert "graduation" in query
    assert "hiking" in query
    assert "curated gift guide" in query


def test_resolve_env_placeholders(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "abc123")
    url = resolve_env_placeholders("https://mcp.serpapi.com/{SERPAPI_KEY}/mcp")
    assert url.endswith("/abc123/mcp")


def test_build_tool_arguments_nested_template():
    from src.mcp.client import McpServerConfig

    config = McpServerConfig(
        tool_name="search",
        arguments={
            "params": {"engine": "google_shopping", "q": "{query}"},
            "mode": "compact",
        },
    )
    args = build_tool_arguments(config, "leather journal gift")
    assert args["params"]["q"] == "leather journal gift"
    assert args["params"]["engine"] == "google_shopping"


def test_web_search_block_includes_exa_label():
    block = web_search_block("1. Trail camera\n2. Daypack")
    assert "Discovery search results" in block
    assert "Exa" in block


def test_search_prompt_includes_discovery_results():
    prompt = search_prompt(
        "Mom",
        "birthday",
        ["gardening"],
        web_results="Herb garden kit — $35",
    )
    assert "Herb garden kit" in prompt


def test_exa_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PRODUCT_SEARCH_ENABLED", "true")
    monkeypatch.setenv("EXA_ENABLED", "false")
    assert is_discovery_enabled() is False


def test_exa_enabled_via_env(monkeypatch):
    monkeypatch.setenv("PRODUCT_SEARCH_ENABLED", "true")
    monkeypatch.setenv("DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("EXA_ENABLED", "true")
    assert is_discovery_enabled() is True


def test_shopping_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PRODUCT_SEARCH_ENABLED", raising=False)
    assert is_product_search_enabled() is False
    assert is_discovery_enabled() is False
    assert is_verification_enabled() is False


def test_shopping_enabled_via_env(monkeypatch):
    monkeypatch.setenv("PRODUCT_SEARCH_ENABLED", "true")
    assert is_product_search_enabled() is True


def test_extract_tool_text_from_blocks():
    block = MagicMock()
    block.text = "Result line one"
    result = MagicMock()
    result.isError = False
    result.content = [block]
    assert extract_tool_text(result) == "Result line one"


def test_parse_retail_snapshot_rainforest_price_dict():
    raw = """
    {
      "results": [
        {
          "title": "Journal",
          "price": {"symbol": "$", "value": 29.99, "raw": "$29.99"},
          "rating": 4.7,
          "link": "https://amazon.com/x"
        }
      ]
    }
    """
    snap = parse_retail_snapshot(raw, "amazon_rainforest")
    assert snap["live_price"] == "$29.99"
    assert snap["amazon_rating"] == 4.7


@patch("src.tools.product_search.retail.call_mcp_tools")
@patch("src.tools.product_search.retail.verify_google_shopping")
def test_verify_gift_retail_merges_sources(mock_google, mock_mcp, monkeypatch):
    monkeypatch.setenv("PRODUCT_SEARCH_ENABLED", "true")
    mock_google.return_value = '{"price":"$19"}'
    mock_mcp.return_value = [
        '{"results":[{"price":"$18","rating":4.5,"link":"https://amazon.com/dp/B001"}]}'
    ]
    out = verify_gift_retail("Leather journal", recipient="Alex")
    assert out["live_price"] == "$18"
    assert out["amazon_rating"] == 4.5
    assert out["amazon_url"] == "https://amazon.com/dp/B001"


def test_exa_discovery_disabled_message(monkeypatch):
    monkeypatch.delenv("PRODUCT_SEARCH_ENABLED", raising=False)
    out = exa_gift_discovery.invoke({"query": "birthday gifts"})
    assert "disabled" in out.lower()


@patch("src.tools.product_search.discovery.discover_gift_ideas")
def test_exa_discovery_returns_results(mock_search, monkeypatch):
    monkeypatch.setenv("PRODUCT_SEARCH_ENABLED", "true")
    mock_search.return_value = "Trending: smart mug"
    out = web_product_search.invoke({"query": "gifts for dad"})
    assert "smart mug" in out


@patch("src.agents.subagents.gift_recommender.graph._llm_json")
@patch("src.agents.subagents.gift_recommender.graph.discover_gift_ideas")
@patch("src.agents.subagents.gift_recommender.graph.is_discovery_enabled", return_value=True)
def test_search_node_uses_exa_discovery(mock_enabled, mock_search, mock_llm):
    mock_search.return_value = "Web hit: leather journal guide"
    mock_llm.return_value = [
        {
            "title": "Leather journal",
            "description": "Handmade",
            "price_range": "$30-50",
            "category": "home",
        }
    ]
    state = {
        "recipient": "Alex",
        "occasion": "birthday",
        "profile_chunks": ["writing"],
        "age_range": None,
        "past_gifts_summary": "",
        "excluded_categories": [],
        "feedback": None,
        "iteration": 1,
    }
    out = search_node(state)
    assert out["search_results"][0]["title"] == "Leather journal"
    assert "Exa+LLM" in out["status"]
    prompt = mock_llm.call_args[0][0]
    assert "leather journal" in prompt.lower()


@patch("src.shared.integration_settings.get_shopping_pipeline_settings")
@patch("src.agents.subagents.gift_recommender.graph.verify_gifts_retail")
@patch("src.agents.subagents.gift_recommender.graph.is_verification_enabled", return_value=True)
def test_verify_node_enriches_top_picks(mock_enabled, mock_verify, mock_settings):
    mock_settings.return_value = {"verify_top_n": 1}
    mock_verify.return_value = [
        {
            "live_price": "$24.99",
            "amazon_rating": 4.8,
            "amazon_url": "https://amazon.com/dp/B001",
        }
    ]
    state = {
        "recipient": "Alex",
        "ranked": [
            {"title": "A", "description": "", "price_range": "$20"},
            {"title": "B", "description": "", "price_range": "$30"},
        ],
        "status": "rank: top 2",
        "error": "",
    }
    out = verify_node(state)
    assert out["ranked"][0]["live_price"] == "$24.99"
    assert out["ranked"][0]["amazon_rating"] == 4.8
    assert out["ranked"][0]["amazon_url"] == "https://amazon.com/dp/B001"
    assert "live_price" not in out["ranked"][1]
    assert mock_verify.call_count == 1
