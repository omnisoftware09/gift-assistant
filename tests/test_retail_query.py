from src.tools.product_search.retail import build_retail_query


def test_build_retail_query_uses_title_only():
    assert build_retail_query("Crossword Puzzle Subscription", recipient="Mom") == (
        "Crossword Puzzle Subscription"
    )
