from scripts.mcp_rainforest_server import _compact_product, _rainforest_request


def test_compact_product_from_search_result():
    item = {
        "title": "Crossword Book",
        "price": {"raw": "$12.99", "value": 12.99, "symbol": "$"},
        "rating": 4.6,
        "asin": "B001TEST",
    }
    compact = _compact_product(item)
    assert compact["price"] == "$12.99"
    assert compact["rating"] == 4.6
    assert compact["link"] == "https://www.amazon.com/dp/B001TEST"


def test_rainforest_request_params_omit_invalid_include_products(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"search_results": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, params):
            captured.update(params)
            return FakeResponse()

    monkeypatch.setenv("RAINFOREST_API_KEY", "test-key")
    monkeypatch.setattr("scripts.mcp_rainforest_server.httpx.Client", FakeClient)

    _rainforest_request(
        {
            "type": "search",
            "amazon_domain": "amazon.com",
            "search_term": "crossword puzzle subscription",
            "number_of_results": 1,
            "exclude_sponsored": "true",
        }
    )

    assert "include_products_count" not in captured
    assert captured["search_term"] == "crossword puzzle subscription"
