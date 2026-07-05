from src.agents.subagents.gift_recommender.agent import (
    _format_single_idea_markdown,
    _gift_recommendation_blocks,
)
from src.interfaces.slack.formatters.limits import SLACK_SECTION_TEXT_MAX
from src.tools.product_search.retail import (
    normalize_display_price,
    parse_retail_snapshot,
    retail_fields_for_display,
)


def test_normalize_display_price_from_rainforest_dict():
    price = normalize_display_price(
        {"symbol": "$", "value": 22.98, "currency": "USD", "raw": "$22.98"}
    )
    assert price == "$22.98"


def test_retail_fields_for_display_strips_raw_json():
    retail = {
        "live_price": "$24.99",
        "amazon_rating": 4.5,
        "retail_amazon": {"raw_excerpt": "x" * 5000},
        "retail_google": {"raw_excerpt": "y" * 5000},
    }
    display = retail_fields_for_display(retail)
    assert display["live_price"] == "$24.99"
    assert display["amazon_rating"] == 4.5
    assert "retail_amazon" not in display


def test_gift_blocks_under_slack_limit():
    ranked = [
        {
            "title": "Leather journal",
            "description": "Handmade " * 200,
            "price_range": "$30",
            "live_price": "$29.99",
            "in_stock": True,
            "purchase_link": "https://amazon.com/dp/B001",
            "reason": "Great fit " * 50,
            "final_score": 88,
            "closeness": 90,
            "rating": 85,
        },
        {
            "title": "Trail camera",
            "description": "Waterproof " * 200,
            "price_range": "$80",
            "live_price": "$79.00",
            "purchase_link": "https://amazon.com/dp/B002",
            "reason": "Outdoor lover " * 50,
            "final_score": 82,
        },
    ]
    blocks = _gift_recommendation_blocks(ranked)
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            text = block["text"].get("text", "")
            assert len(text) <= SLACK_SECTION_TEXT_MAX


def test_single_idea_markdown_shows_price_and_rating_only():
    md = _format_single_idea_markdown(
        {
            "title": "Mug",
            "live_price": "$15.00",
            "amazon_rating": 4.6,
            "amazon_url": "https://amazon.com/dp/ABC",
            "description": "Should not appear",
            "reason": "Should not appear",
            "rating": 88,
            "final_score": 90,
        },
        1,
    )
    assert md == "*1. Mug* · $15.00 · ★4.6"
    assert "Should not appear" not in md
    assert "score" not in md


def test_gift_block_includes_amazon_detail_button():
    blocks = _gift_recommendation_blocks(
        [
            {
                "title": "Mug",
                "description": "Ceramic",
                "live_price": "$15",
                "amazon_rating": 4.6,
                "amazon_url": "https://amazon.com/dp/ABC",
                "reason": "Fun",
            }
        ]
    )
    gift_block = blocks[-1]
    assert gift_block["type"] == "section"
    accessory = gift_block["accessory"]
    assert accessory["type"] == "button"
    assert accessory["url"] == "https://amazon.com/dp/ABC"
    assert accessory["text"]["text"] == "Amazon details"


def test_gift_block_omits_button_without_url():
    blocks = _gift_recommendation_blocks(
        [{"title": "Mug", "description": "Ceramic", "price_range": "$15", "reason": "Fun"}]
    )
    assert "accessory" not in blocks[-1]
