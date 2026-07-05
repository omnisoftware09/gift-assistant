# Shopping Pipeline (Discovery + Verification)

Gift recommendations use a **two-phase shopping pipeline** inspired by discovery-then-verify workflows:

1. **Discovery (Exa MCP)** — search the web for creative, human-curated gift lists based on recipient + profile
2. **Verification (Retail MCP)** — after ranking, check live prices, stock, and purchase links via:
   - **Google Shopping** (SerpApi hosted MCP)
   - **Amazon Rainforest** (local stdio MCP wrapper around Rainforest API)

## Enable

```bash
pip install -r requirements.txt

export PRODUCT_SEARCH_ENABLED=true
export EXA_ENABLED=true
export EXA_API_KEY=your_exa_key          # optional but recommended (rate limits)
export SERPAPI_KEY=your_serpapi_key      # Google Shopping verification
export RAINFOREST_API_KEY=your_rainforest_key  # Amazon verification
```

Exa works without an API key at `https://mcp.exa.ai/mcp` (free tier with limits).

## Configuration

`config/integrations.yaml`:

```yaml
product_search:
  enabled: false
  pipeline:
    discovery_enabled: true
    verification_enabled: true
    verify_top_n: 3
  servers:
    exa:
      transport: http
      url: https://mcp.exa.ai/mcp
      tool_name: web_search_exa
    google_shopping:
      transport: http
      url: https://mcp.serpapi.com/{SERPAPI_KEY}/mcp
      tool_name: search
      arguments:
        params:
          engine: google_shopping
          q: "{query}"
        mode: compact
    amazon_rainforest:
      transport: stdio
      command: python
      args: [scripts/mcp_rainforest_server.py]
      tool_name: amazon_product_search
      tool_argument_key: search_term
```

| Variable | Purpose |
|----------|---------|
| `PRODUCT_SEARCH_ENABLED` | Master switch |
| `EXA_ENABLED` | Turn Exa discovery on/off (`true` / `false`) |
| `EXA_API_KEY` | Exa MCP header `x-api-key` (optional; improves rate limits) |
| `EXA_MCP_URL` | Override Exa MCP URL (default `https://mcp.exa.ai/mcp`) |
| `DISCOVERY_ENABLED` | Discovery phase (Exa) when master switch is on |
| `VERIFICATION_ENABLED` | Google Shopping + Amazon phase |
| `VERIFY_TOP_N` | How many ranked gifts get retail checks (default 3) |
| `SERPAPI_KEY` | SerpApi hosted MCP URL + Google Shopping engine |
| `RAINFOREST_API_KEY` | Rainforest Amazon API (stdio MCP wrapper) |

## Pipeline flow

```
LangGraph gift recommender
  search   → Exa MCP discovery → LLM proposes 5 gift ideas
  evaluate → LLM ratings + profile closeness
  rank     → top 3 by weighted score
  verify   → Google Shopping MCP + Amazon Rainforest MCP per top pick
```

Each verified gift may include:

- `live_price` — Amazon price from Rainforest
- `amazon_rating` — Amazon star rating (e.g. 4.5)

## LangChain tools

Exported as `GIFT_SEARCH_TOOLS` / `PRODUCT_SEARCH_TOOLS`:

- `exa_gift_discovery` — discovery phase
- `google_shopping_verify` — Google Shopping verification
- `amazon_rainforest_verify` — Amazon Rainforest verification

## Rainforest MCP wrapper

Rainforest API does not ship an official MCP server. This repo includes `scripts/mcp_rainforest_server.py`, a thin stdio MCP server that exposes:

- `amazon_product_search(search_term, max_results=3)`
- `amazon_product_lookup(asin)`

Run standalone for debugging:

```bash
export RAINFOREST_API_KEY=your_key
python scripts/mcp_rainforest_server.py
```

## Fallback

- Discovery disabled or failing → LLM-only gift ideas (same as before MCP)
- Verification disabled or failing → ranked ideas without live prices/links
- Either retail server can fail independently; the other still enriches results
