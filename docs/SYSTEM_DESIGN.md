# Gift Assistant — System Design

Final design documentation for demos, reviews, and onboarding.

---

## 1. Overview

Gift Assistant is a **Slack-native, multi-agent gift concierge**. A central **orchestrator** receives every user message and routes it to one of four specialized sub-agents. The core design is a **discovery → evaluate → verify** gift pipeline: the LLM generates creative ideas, scoring filters them against stored knowledge, and external MCP tools ground the top results in live retail data.

The system runs as a long-lived Python process (`src/main.py`) using **Slack Socket Mode**, with a background worker for proactive calendar alerts.

### What it is designed to do

- Help users find **personalized gifts** for people they care about
- Remember **interests, past gifts, and occasions** across conversations
- **Proactively alert** users before gift-relevant calendar events
- **Verify** top recommendations with live Amazon/Google Shopping price and ratings
- Support **refinement** — users can give feedback and get better ideas in the next round

### What successful performance looks like

| For users | For the system |
|-----------|----------------|
| Recommendations feel personal, not generic | Pipeline completes: search → evaluate → rank → verify |
| No repeat gifts from past selections | Chroma returns relevant profile chunks |
| Top picks show real price and star rating | Retail verification succeeds without quota burn |
| One-reply refinement improves results | Sessions stay coherent when recipient changes |
| Proactive nudge → one click to gift search | Slack messages render without errors |

### Important boundaries

- **Suggests only** — no checkout, purchasing, or shipping
- **Fixed gift pipeline** — not open-ended agent loops (predictable, debuggable, cost-controlled)
- **Shopping APIs optional** — Exa, Google Shopping, Rainforest each toggleable via env
- **Verify top N only** — caps retail API calls (`VERIFY_TOP_N`)
- **Read-only calendar** — Google Calendar API, not Google MCP in production
- **Profile-dependent quality** — sparse profiles produce more general ideas

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SLACK INTERFACE                          │
│   DMs · Mentions · /gift · /events · /ecard · Alert Buttons    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                               │
│   Intent routing · Session management · Recipient handoff       │
└──┬──────────────┬──────────────┬──────────────┬─────────────────┘
   │              │              │              │
   ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│  Gift    │ │ Profile  │ │  Event   │ │   eCard      │
│Recommender│ │Collector │ │ Monitor  │ │  Generator   │
│LangGraph │ │  ReAct   │ │          │ │              │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
     │            │            │               │
     ▼            ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MEMORY & DATA LAYER                        │
│  Gift Sessions (JSON) · Gift History (SQLite) · Profiles (Chroma)│
│  Notification Store (JSON)                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TOOLS & MCP LAYER                          │
│  Exa (discovery) · SerpApi (Google Shopping) · Rainforest (Amazon)│
│  Google Calendar API · Chroma profile tools                     │
└─────────────────────────────────────────────────────────────────┘
```

See `docs/architecture-diagram.svg` for a visual version suitable for Google Slides.

---

## 3. Major Components

### 3.1 Slack Interface

- **Socket Mode** — no public URL required
- **Handlers** — messages, slash commands, interactive buttons
- **Formatters** — Block Kit with truncation, per-gift sections, Amazon detail buttons, `unfurl_links=false`

### 3.2 Orchestrator

Entry point for all user messages (`src/agents/orchestrator/agent.py`):

- **Intent detection** — regex + keyword routing (gift, profile, calendar, eCard)
- **Session priority** — active gift/eCard sessions checked before new intent parsing
- **Recipient handoff** — different recipient mid-session clears stale state
- **Direct tool calls** — loads recipient context from SQLite before gift search

### 3.3 Gift Recommender (core pipeline)

Fixed **LangGraph** with four nodes (`src/agents/subagents/gift_recommender/graph.py`):

| Node | Purpose |
|------|---------|
| **search** | LLM generates 5 gift ideas; optional Exa discovery injected as inspiration |
| **evaluate** | LLM rates each idea 0–100; embedding closeness vs profile chunks |
| **rank** | Weighted sort: **70% closeness + 30% rating** → top 3 |
| **verify** | MCP retail lookup on top N — live price, star rating, purchase link |

**Not ReAct** — tools are called programmatically in nodes; the gift LLM does not choose which MCP tool to call.

### 3.4 Profile Collector

Only sub-agent using **ReAct** (`create_react_agent`). LLM decides when to call Chroma tools to save, query, or delete recipient profiles.

### 3.5 Event Monitor + Proactive Worker

- **Event Monitor** — answers calendar queries
- **Background scheduler** — scans upcoming events, DMs user with gift-relevant alerts and buttons
- Uses **Google Calendar API** directly for production reliability

### 3.6 eCard Generator

Separate flow for visual greeting cards — LLM copy, image generation, Slack file upload.

### 3.7 Memory Layer

| Store | Type | Purpose |
|-------|------|---------|
| Gift sessions | JSON | Short-term: recipient, iteration, feedback, last ranked ideas |
| Gift history | SQLite | Long-term: selected gifts, categories, age ranges |
| ChromaDB profiles | Vector DB | Chunked interest text, semantically retrieved per occasion |
| Notification store | JSON | Calendar alerts sent/snoozed/skipped |

### 3.8 MCP Tool Layer

Configured in `config/integrations.yaml`, toggleable via env:

| Server | Transport | Purpose |
|--------|-----------|---------|
| Exa | HTTP | Discovery — gift list articles |
| SerpApi | HTTP | Google Shopping verification |
| Rainforest | stdio | Amazon search via local wrapper |

**Circuit breaker** — stops further MCP calls in a batch after quota or API errors.

---

## 4. End-to-End Gift Flow

```
User: "recommend gift for Mom's birthday"
         │
         ▼
Orchestrator
  · Parse gift request
  · Load SQLite history for Mom
  · Clear stale session if recipient changed
         │
         ▼
Gift Recommender
  · RETRIEVE: ChromaDB → profile chunks for Mom + occasion
  · SEARCH: optional Exa → LLM → 5 candidates
  · EVALUATE: LLM ratings + embedding closeness
  · RANK: 0.7×closeness + 0.3×rating → top 3
  · VERIFY: Rainforest/Shopping on top N → price, rating, link
         │
         ▼
Slack Response
  · Block Kit: profile + 3 gifts with price/★
  · Amazon details button per gift
  · "Reply 1/2/3 · feedback to refine · done"
         │
         ▼
Human in the loop
  · Pick 1/2/3 → save to history
  · Feedback → re-run pipeline
  · Done → clear session
```

---

## 5. Design Dimensions

### 5.1 Reasoning loops

- **Gift pipeline**: fixed linear LangGraph — one LLM call per search/evaluate node
- **Refinement loop**: user feedback triggers full pipeline re-run with accumulated session feedback
- **Profile Collector**: ReAct loop — LLM chooses profile tools

**Tree-of-Thought: not used.** Structured pipeline + scoring + retrieval fits gift recommendation better than branching reasoning trees.

### 5.2 Memory

- **Working memory** — `GiftSession`: recipient, feedback, iteration, last ranked results
- **Episodic memory** — SQLite: every selected gift with category and occasion
- **Semantic memory** — ChromaDB: chunked profiles retrieved by embedding similarity
- **Procedural memory** — excluded categories derived from past gift history

### 5.3 Tools

| Tool | Called by | When |
|------|-----------|------|
| Chroma `query_profile` | Gift agent | Every gift request |
| Exa `web_search_exa` | search node | If `EXA_ENABLED` |
| Rainforest `amazon_product_search` | verify node | If `AMAZON_RAINFOREST_ENABLED` |
| SerpApi `search` | verify node | If `GOOGLE_SHOPPING_ENABLED` |
| Calendar `read_events` | Event monitor | Queries + proactive worker |
| Profile save/query/delete | Profile Collector | User shares or asks about interests |

### 5.4 Retrieval

1. **Profile** (ChromaDB) — semantic search over interest chunks, filtered by recipient
2. **Discovery** (Exa) — web search for gift articles; inspiration only, not copied as products
3. **Retail** (Rainforest/Shopping) — live product lookup for top-ranked ideas

### 5.5 Multi-agent coordination

- **Orchestrator pattern** — single entry point; orchestrator calls sub-agents directly
- **Session-aware routing** — active sessions take priority
- **Shared memory** — all agents read ChromaDB and SQLite; gift history written on selection
- **Proactive → reactive** — calendar worker DMs user; button → orchestrator → gift recommender

### 5.6 Guardrails

| Layer | Mechanism |
|-------|-----------|
| Prompt | No repeat gifts; penalize excluded categories (rating < 40) |
| Scoring | Weighted rank prevents LLM-only picks from dominating |
| Parsing | JSON extraction with fallback candidates |
| API | MCP circuit breaker; `VERIFY_TOP_N`; env toggles |
| Session | Recipient mismatch clears stale state |
| Output | Slack truncation, price normalization, `unfurl_links=false` |
| Storage | Empty/invalid JSON stores handled gracefully |

### 5.7 Logging & observability

- **Local logging** — pipeline nodes log recipient, scores, MCP results at INFO
- **LangSmith** — `@trace_agent` / `@trace_tool` when `LANGCHAIN_TRACING_V2=true`
- **Lifecycle** — `agent.start`, `agent.success`, `agent.error` with elapsed ms

### 5.8 Evaluation

1. **LLM evaluation** — 0–100 rating per candidate with reason
2. **Embedding evaluation** — cosine similarity vs profile chunks (closeness 0–100)
3. **Weighted fusion** — `0.7 × closeness + 0.3 × rating`
4. **Retail grounding** — verify node adds price/rating from external APIs
5. **Human evaluation** — pick 1/2/3 or feedback → re-run

### 5.9 Human intervention

| Action | System response |
|--------|-----------------|
| Pick 1/2/3 | Save to SQLite → clear session → exclude category next time |
| Give feedback | Append to session → re-run pipeline |
| Say "done" | Clear session without saving |
| Share interests | Profile Collector → ChromaDB |
| Click alert button | Proactive worker → gift search |
| Snooze / Skip | Notification store updated |

---

## 6. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Fixed LangGraph over ReAct for gifts | Predictable cost, debuggable, no runaway tool loops |
| Programmatic MCP calls | Gift LLM focuses on ideas; tools are infrastructure |
| Discovery separate from verification | Exa inspires; Rainforest grounds in real products |
| SQLite for history, Chroma for profiles | Structured records vs semantic search |
| Socket Mode Slack | No public URL infra; runs on a laptop |
| Human-in-the-loop by default | Gift choice is subjective; system proposes, user decides |

---

## 7. How We Built the System

Gift Assistant is a **Python Slack bot** built in layers: Slack interface → orchestrator routing → agent pipelines → memory → external APIs/MCP tools.

### Build approach

1. **Slack-first interface** — Bolt app with Socket Mode (no public URL)
2. **Orchestrator routing** — keyword/parser-based intent detection, session management
3. **Gift pipeline** — fixed LangGraph (`search → evaluate → rank → verify`)
4. **Memory** — ChromaDB (profiles), SQLite (gift history), JSON (sessions/alerts)
5. **External grounding** — MCP for web discovery and retail verification
6. **Observability** — logging + LangSmith tracing from the start

### Interface and runtime

| Technology | Role | How it supports design |
|------------|------|------------------------|
| **Python 3.10+** | Core language | Single process; strong ML/AI ecosystem |
| **Slack Bolt** (`slack-bolt`) | Slack SDK + event handlers | DMs, mentions, slash commands, Block Kit buttons |
| **Socket Mode** | Outbound WebSocket to Slack | Runs locally without ngrok; laptop-friendly dev |
| **python-dotenv** | Config from `.env` | Swap LLM keys and API toggles without code changes |
| **PyYAML** | `config/*.yaml` | Agents, integrations, LLM settings in versioned config |

### Orchestration and agents

| Technology | Role | How it supports design |
|------------|------|------------------------|
| **LangGraph** (`langgraph`) | Gift pipeline state machine | Fixed `search → evaluate → rank → verify` — predictable, debuggable |
| **LangGraph ReAct** (`create_react_agent`) | Profile Collector only | LLM chooses when to save/query profiles |
| **LangChain Core** | Messages, tools, prompts | Shared LLM interface across agents |
| **Custom orchestrator** | Python router (no LLM) | Fast, cheap routing; session priority over intent |

### Models (swappable via env)

| Provider | Library | Default model | Use |
|----------|---------|---------------|-----|
| **OpenAI** | `langchain-openai` | `gpt-4o-mini` | Gift search/evaluate, eCard copy |
| **Anthropic** | `langchain-anthropic` | `claude-3-5-haiku-latest` | Alternative chat LLM |
| **Ollama** | `langchain-ollama` | `llama3.2` (local) | Offline/dev without API keys |
| **OpenAI Embeddings** | `langchain-openai` | `text-embedding-3-small` | Profile retrieval, gift closeness scoring |
| **Ollama Embeddings** | `langchain-ollama` | `nomic-embed-text` | Local embedding option |
| **OpenAI Images** | eCard module | `gpt-image-1-mini` | Optional eCard backgrounds |
| **Pillow** | `Pillow` | — | Free local eCard backgrounds |

`get_chat_model()` and `get_embeddings()` factories switch providers via `LLM_PROVIDER` / `EMBEDDING_PROVIDER` — no code changes.

### Memory and retrieval

| Technology | Role | How it supports design |
|------------|------|------------------------|
| **ChromaDB** + **langchain-chroma** | Vector store for profiles | Semantic retrieval of interest chunks per recipient/occasion |
| **SQLite** (`stdlib sqlite3`) | Gift history, age ranges | Structured anti-repeat memory; excluded categories |
| **JSON files** | Sessions, notification state | Lightweight short-term state without a DB server |

### External APIs and MCP tools

| API / service | Library / transport | Role | How it supports design |
|---------------|---------------------|------|------------------------|
| **Exa MCP** | HTTP MCP (`mcp` + `httpx`) | Web discovery | Gift list articles as LLM inspiration |
| **SerpApi MCP** | HTTP MCP | Google Shopping | Retail price verification |
| **Rainforest API** | Custom stdio MCP (`FastMCP` + `httpx`) | Amazon search | Live price, rating, link for top gifts |
| **Google Calendar API** | `google-api-python-client`, OAuth | Calendar read | Event queries + proactive alerts |
| **MCP SDK** (`mcp>=1.8.0`) | stdio + HTTP clients | Tool protocol | One client for Exa, SerpApi, Rainforest; batch + circuit breaker |

Rainforest has no official MCP server — we built a thin **stdio wrapper** (`scripts/mcp_rainforest_server.py`) so Amazon fits the same MCP pattern as Exa and SerpApi.

### Observability and testing

| Technology | Role | How it supports design |
|------------|------|------------------------|
| **LangSmith** (`langsmith`) | Tracing | `@trace_agent` / `@trace_tool` on pipeline steps |
| **Python logging** | Local logs | `agent.start`, `agent.success`, pipeline node INFO |
| **pytest** | 93 unit/integration tests | Mock LLM/MCP for deterministic pipeline validation |

### How the stack maps to design choices

```
Slack Bolt          →  User talks in Slack; Block Kit for rich gift cards
Orchestrator        →  Routes to the right agent; manages sessions
LangGraph (gift)    →  Fixed pipeline, not open ReAct — cost + reliability
LangGraph (profile) →  ReAct only where tool choice matters
ChromaDB            →  "What does Sarah like?" — semantic profile retrieval
SQLite              →  "What did we give before?" — structured anti-repeat memory
Exa MCP             →  Discovery — creative inspiration from the web
Rainforest MCP      →  Verification — real Amazon price/rating
Google Calendar API →  Proactive nudges before birthdays
LangSmith           →  Trace every agent step for debugging
```

### Tech stack summary

| Layer | Technology |
|-------|------------|
| Interface | Slack Bolt, Socket Mode, Block Kit |
| Orchestration | Python orchestrator, intent routing |
| Gift pipeline | LangGraph (search → evaluate → rank → verify) |
| Profile agent | LangGraph ReAct |
| LLM | OpenAI / Anthropic / Ollama (swappable via env) |
| Embeddings | OpenAI / Ollama (`nomic-embed-text`) |
| Vector DB | ChromaDB |
| Structured data | SQLite (gift history) |
| Session/state | JSON files |
| External tools | MCP (Exa, SerpApi, Rainforest stdio) |
| Calendar | Google Calendar API |
| Observability | Python logging + LangSmith |
| Testing | pytest (93 tests) |

---

## 8. Configuration

Key environment variables:

```env
# Core
SLACK_BOT_TOKEN=...
SLACK_APP_TOKEN=...

# LLM (pick one)
LLM_PROVIDER=openai|anthropic|ollama

# Shopping pipeline
PRODUCT_SEARCH_ENABLED=true
EXA_ENABLED=false
GOOGLE_SHOPPING_ENABLED=false
AMAZON_RAINFOREST_ENABLED=true
RAINFOREST_API_KEY=...
VERIFY_TOP_N=1

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
```

See `docs/PRODUCT_SEARCH.md` for full MCP setup.

---

## 9. Evaluation

See [EVALUATION.md](EVALUATION.md) for test coverage, manual scenarios, main results, and known limitations.

---

## 10. Project Structure (relevant paths)

```
gift-assistant/
├── src/
│   ├── main.py                          # Entry point
│   ├── agents/
│   │   ├── orchestrator/                # Routing + sessions
│   │   └── subagents/
│   │       ├── gift_recommender/        # LangGraph pipeline
│   │       ├── profile_collector/       # ReAct agent
│   │       ├── event_monitor/
│   │       └── ecard_generator/
│   ├── mcp/client.py                    # MCP stdio + HTTP client
│   ├── tools/
│   │   ├── product_search/              # Discovery + retail
│   │   └── vector_db/                   # Chroma profiles
│   ├── shared/                          # Sessions, settings, stores
│   ├── storage/gift_history/            # SQLite
│   └── interfaces/slack/                # Handlers, formatters
├── scripts/mcp_rainforest_server.py     # Amazon MCP wrapper
├── config/
│   ├── agents.yaml
│   └── integrations.yaml
└── docs/
    ├── SYSTEM_DESIGN.md                 # This document
    ├── EVALUATION.md                    # Test coverage and results
    ├── DEMO_SLIDE_CONTENT.md            # Slide copy
    └── architecture-diagram.svg         # Upload to Google Slides
```
