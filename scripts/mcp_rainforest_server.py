#!/usr/bin/env python3
"""
stdio MCP server wrapping Rainforest API for Amazon product search.

Rainforest API does not ship an official MCP server; this thin wrapper exposes
Amazon search + product details as MCP tools for the gift verification phase.

Requires: pip install mcp httpx
Env: RAINFOREST_API_KEY
"""

from __future__ import annotations

import json
import os
import sys

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - runtime guard for script
    print(
        "Missing dependency 'mcp'. Install with: pip install mcp httpx",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

mcp = FastMCP("rainforest-amazon")
RAINFOREST_URL = "https://api.rainforestapi.com/request"


def _api_key() -> str:
    key = os.getenv("RAINFOREST_API_KEY", "").strip()
    if not key:
        raise RuntimeError("RAINFOREST_API_KEY is required")
    return key


def _rainforest_request(params: dict) -> dict:
    query = {"api_key": _api_key(), **params}
    with httpx.Client(timeout=30.0) as client:
        response = client.get(RAINFOREST_URL, params=query)
        if response.status_code in (402, 429):
            return {
                "error": "quota_exceeded",
                "status_code": response.status_code,
                "message": response.text[:300],
            }
        if response.status_code >= 400:
            message = response.text[:500]
            try:
                payload = response.json()
                message = payload.get("request_info", {}).get("message") or str(payload)[:500]
            except Exception:
                pass
            return {
                "error": "api_error",
                "status_code": response.status_code,
                "message": message,
            }
        return response.json()


def _compact_product(item: dict) -> dict:
    product = item.get("product") or item
    price_raw = product.get("price") or item.get("price")
    price = None
    if isinstance(price_raw, dict):
        price = price_raw.get("raw")
        if not price and price_raw.get("value") is not None:
            symbol = price_raw.get("symbol") or "$"
            price = f"{symbol}{float(price_raw['value']):.2f}"
    elif price_raw is not None:
        price = str(price_raw)

    rating = (
        product.get("rating")
        or item.get("rating")
        or item.get("rating_stars")
    )
    if isinstance(rating, dict):
        rating = rating.get("value") or rating.get("stars")

    link = product.get("link") or item.get("link")
    if not link and item.get("asin"):
        link = f"https://www.amazon.com/dp/{item['asin']}"

    return {
        "title": product.get("title") or item.get("title"),
        "price": price,
        "link": link,
        "asin": product.get("asin") or item.get("asin"),
        "rating": rating,
    }


@mcp.tool()
def amazon_product_search(search_term: str, max_results: int = 3) -> str:
    """
    Search Amazon for products by keyword.
    Returns compact JSON with title, price, stock, and purchase links.
    """
    data = _rainforest_request(
        {
            "type": "search",
            "amazon_domain": "amazon.com",
            "search_term": search_term.strip(),
            "number_of_results": 1,
            "exclude_sponsored": "true",
        }
    )

    if data.get("error") in ("quota_exceeded", "api_error"):
        return json.dumps({"error": data["error"], "results": [], "message": data.get("message")})

    results = []
    for item in data.get("search_results") or []:
        results.append(_compact_product(item))
        if len(results) >= max_results:
            break

    if not results and data.get("product"):
        results.append(_compact_product(data))

    return json.dumps({"search_term": search_term, "results": results}, indent=2)


@mcp.tool()
def amazon_product_lookup(asin: str) -> str:
    """Fetch live Amazon product details by ASIN (price, stock, link)."""
    data = _rainforest_request(
        {
            "type": "product",
            "amazon_domain": "amazon.com",
            "asin": asin,
        }
    )
    product = _compact_product(data.get("product") or data)
    return json.dumps({"asin": asin, "product": product}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
