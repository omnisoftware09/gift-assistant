"""Verification phase — Google Shopping + Amazon Rainforest retail MCP tools."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.tools import tool

from src.mcp.client import McpServerConfig, call_mcp_server, call_mcp_tools
from src.shared.integration_settings import get_shopping_pipeline_settings, is_verification_enabled

logger = logging.getLogger("gift_assistant.product_search.retail")


def build_retail_query(gift_title: str, recipient: str | None = None) -> str:
    """Amazon search query — use gift title only (recipient name confuses product search)."""
    return gift_title.strip()


def verify_google_shopping(query: str) -> str:
    if not is_verification_enabled():
        return ""

    settings = get_shopping_pipeline_settings()
    server = settings["google_shopping"]
    if not server:
        return ""

    return call_mcp_server(server, query)


def verify_amazon_rainforest(query: str) -> str:
    if not is_verification_enabled():
        return ""

    settings = get_shopping_pipeline_settings()
    server = settings["amazon_rainforest"]
    if not server:
        return ""

    return call_mcp_server(server, query)


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_json_blob(text: str) -> Any | None:
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start_obj = cleaned.find("{")
        start_arr = cleaned.find("[")
        starts = [s for s in (start_obj, start_arr) if s != -1]
        if not starts:
            return None
        start = min(starts)
        end_obj = cleaned.rfind("}")
        end_arr = cleaned.rfind("]")
        end = max(end_obj, end_arr)
        if end <= start:
            return None
        cleaned = cleaned[start : end + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _normalize_star_rating(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("stars") or value.get("rating")
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if rating <= 0 or rating > 5:
        return None
    return round(rating, 1)


def normalize_display_price(value: Any) -> str | None:
    """Turn Rainforest/Google price objects into a clean string like $22.98."""
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        raw = value.get("raw")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        amount = value.get("value")
        symbol = str(value.get("symbol") or "$")
        if amount is not None:
            try:
                return f"{symbol}{float(amount):.2f}"
            except (TypeError, ValueError):
                pass
        return None
    if isinstance(value, (int, float)):
        return f"${float(value):.2f}"
    text = str(value).strip()
    if not text or text.startswith("{") or text.startswith("("):
        return None
    if text.startswith("$"):
        return text
    if re.fullmatch(r"[0-9]+(?:\.[0-9]{2})?", text):
        return f"${text}"
    return text


def _extract_link(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value
    return None


def _rainforest_primary_result(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0]
    product = data.get("product")
    if isinstance(product, dict):
        return product
    return None


def _pick_product_fields(data: Any) -> dict[str, Any]:
    """Best-effort extraction of price, rating, stock, and link from MCP JSON/text."""

    primary = _rainforest_primary_result(data)
    if primary:
        price = normalize_display_price(primary.get("price"))
        link = _extract_link(primary.get("link"))
        rating = _normalize_star_rating(primary.get("rating"))
        title = str(primary.get("title") or "").strip() or None
        if price or link or rating:
            return {
                "product_title": title,
                "live_price": price,
                "amazon_rating": rating,
                "purchase_link": link,
                "in_stock": None,
                "stock_note": None,
            }

    candidates: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            title = node.get("title") or node.get("name") or node.get("product_title")
            price = normalize_display_price(
                node.get("price")
                or node.get("extracted_price")
                or node.get("price_str")
                or node.get("price_raw")
            )
            link = _extract_link(
                node.get("link")
                or node.get("product_link")
                or node.get("url")
                or node.get("amazon_url")
            )
            rating = _normalize_star_rating(
                node.get("rating") or node.get("stars") or node.get("star_rating")
            )
            if title or price or link or rating is not None:
                candidates.append(
                    {
                        "title": str(title or "").strip(),
                        "price": price,
                        "link": link,
                        "rating": rating,
                    }
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    if not candidates:
        return {}

    best = candidates[0]
    for item in candidates:
        if item.get("price") and item.get("rating") is not None:
            best = item
            break
        if item.get("price"):
            best = item

    return {
        "product_title": best.get("title") or None,
        "live_price": best.get("price") or None,
        "amazon_rating": best.get("rating"),
        "purchase_link": best.get("link") or None,
        "in_stock": None,
        "stock_note": None,
    }


def parse_retail_snapshot(raw: str, source: str) -> dict[str, Any]:
    """Normalize Google Shopping / Amazon MCP output into gift fields."""
    if not raw or not raw.strip():
        return {"source": source, "raw": ""}

    parsed = _parse_json_blob(raw)
    fields = _pick_product_fields(parsed) if parsed is not None else {}

    if not fields.get("live_price"):
        extracted = _first_match(
            r'"raw"\s*:\s*"(\$[0-9.]+)"|"extracted_price"\s*:\s*([0-9.]+)|"price"\s*:\s*"(\$[^"]+)"',
            raw,
        )
        fields["live_price"] = normalize_display_price(extracted)
    if fields.get("amazon_rating") is None:
        rating_match = _first_match(r'"rating"\s*:\s*([0-9.]+)', raw)
        fields["amazon_rating"] = _normalize_star_rating(rating_match)
    if fields.get("in_stock") is None:
        lower = raw.lower()
        if "out of stock" in lower or "unavailable" in lower:
            fields["in_stock"] = False
        elif "in stock" in lower:
            fields["in_stock"] = True

    fields["source"] = source
    fields["raw_excerpt"] = raw[:1200]
    return fields


# Fields merged onto ranked gifts for Slack display (exclude raw MCP payloads).
RETAIL_DISPLAY_FIELDS = (
    "live_price",
    "amazon_rating",
    "amazon_url",
)


def retail_fields_for_display(retail: dict) -> dict[str, object]:
    """Strip bulky MCP JSON before attaching retail data to gift ideas."""
    out: dict[str, object] = {}
    for key in RETAIL_DISPLAY_FIELDS:
        value = retail.get(key)
        if value is None:
            continue
        if key == "live_price":
            value = normalize_display_price(value)
            if not value:
                continue
        out[key] = value
    return out


def _retail_from_snapshots(amazon: dict, google: dict) -> dict[str, Any]:
    live_price = normalize_display_price(amazon.get("live_price")) or normalize_display_price(
        google.get("live_price")
    )
    amazon_rating = amazon.get("amazon_rating") or google.get("amazon_rating")
    amazon_url = amazon.get("purchase_link") or google.get("purchase_link")
    return {
        "live_price": live_price,
        "amazon_rating": amazon_rating,
        "amazon_url": amazon_url,
        "retail_google": google,
        "retail_amazon": amazon,
    }


def verify_gifts_retail(
    gift_titles: list[str],
    *,
    recipient: str | None = None,
) -> list[dict[str, Any]]:
    """Verify multiple gifts — one Rainforest MCP session, stops on quota errors."""
    if not gift_titles or not is_verification_enabled():
        return [{} for _ in gift_titles]

    settings = get_shopping_pipeline_settings()
    amazon_cfg = settings["amazon_rainforest"]
    google_cfg = settings["google_shopping"]

    amazon_raws: list[str] = [""] * len(gift_titles)
    if amazon_cfg:
        calls: list[tuple[str, dict[str, Any]]] = []
        for title in gift_titles:
            query = build_retail_query(title, recipient)
            arg_key = amazon_cfg.tool_argument_key or "search_term"
            calls.append((amazon_cfg.tool_name, {arg_key: query}))
        try:
            amazon_raws = call_mcp_tools(amazon_cfg, calls)
        except Exception:
            logger.exception("Amazon Rainforest MCP batch failed")
            amazon_raws = [""] * len(gift_titles)

    quota_warned = False
    results: list[dict[str, Any]] = []
    for index, title in enumerate(gift_titles):
        amazon_raw = amazon_raws[index] if index < len(amazon_raws) else ""
        if amazon_raw and "quota_exceeded" in amazon_raw and not quota_warned:
            logger.warning(
                "Rainforest API quota exceeded (402) — add credits at "
                "https://trajectdata.com or lower VERIFY_TOP_N in .env"
            )
            quota_warned = True
        if amazon_raw and "api_error" in amazon_raw and not quota_warned:
            logger.warning(
                "Rainforest API request failed — gift will show without Amazon price/rating"
            )
            quota_warned = True

        google_raw = ""
        if google_cfg:
            try:
                google_raw = verify_google_shopping(build_retail_query(title, recipient))
            except Exception:
                logger.exception("Google Shopping MCP failed for %r", title)

        amazon = parse_retail_snapshot(amazon_raw, "amazon_rainforest") if amazon_raw else {}
        google = parse_retail_snapshot(google_raw, "google_shopping") if google_raw else {}
        results.append(_retail_from_snapshots(amazon, google))

    return results


def verify_gift_retail(
    gift_title: str,
    *,
    recipient: str | None = None,
) -> dict[str, Any]:
    """Run Google Shopping + Amazon Rainforest MCP for one gift idea."""
    results = verify_gifts_retail([gift_title], recipient=recipient)
    return results[0] if results else {}


@tool
def google_shopping_verify(query: str) -> str:
    """Verification-phase Google Shopping search for live prices and purchase links."""
    try:
        result = verify_google_shopping(query)
        return result or "Google Shopping verification is disabled."
    except Exception as exc:
        logger.exception("google_shopping_verify failed")
        return f"Google Shopping search failed: {exc}"


@tool
def amazon_rainforest_verify(query: str) -> str:
    """Verification-phase Amazon search via Rainforest MCP for prices, stock, and links."""
    try:
        result = verify_amazon_rainforest(query)
        return result or "Amazon Rainforest verification is disabled."
    except Exception as exc:
        logger.exception("amazon_rainforest_verify failed")
        return f"Amazon Rainforest search failed: {exc}"
