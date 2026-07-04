# Observability — LangSmith Tracing for All Agents

Every agent and tool in Gift Assistant is traced with **LangSmith** for debugging, logging, and monitoring.

---

## What gets traced

| Component | LangSmith run name | Type |
|-----------|-------------------|------|
| Orchestrator (DM / @mention) | `orchestrator` | chain |
| Slash commands | `orchestrator.slash_command` | chain |
| Gift Recommender | `gift_recommender` | chain |
| Event Monitor | `event_monitor` | chain |
| Proactive alerts worker | `proactive_worker` | tool |
| Google Calendar fetch | `calendar.fetch_events_between` | tool |
| Future: Profile Collector | `profile_collector` | chain |
| Future: eCard Generator | `ecard_generator` | chain |
| Future: Chroma tools | `chroma.*` | tool |
| Future: LangGraph ReAct loops | nested runs auto-traced | chain / llm / tool |

---

## Setup (5 minutes)

### 1. Create a LangSmith account

1. Go to [smith.langchain.com](https://smith.langchain.com)
2. Sign up (free tier available)
3. Create a project named **`gift-assistant`**

### 2. Get your API key

1. LangSmith → **Settings** → **API Keys**
2. Create key → copy it (starts with `lsv2_pt_...`)

### 3. Add to `.env`

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your-key-here
LANGCHAIN_PROJECT=gift-assistant
LOG_LEVEL=INFO
```

### 4. Install dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Restart the bot

```bash
python -m src.main
```

You should see in the terminal:
```
LangSmith tracing enabled — project=gift-assistant
```

### 6. View traces

1. Send a message in Slack: `what events today?`
2. Open [smith.langchain.com](https://smith.langchain.com) → **gift-assistant** project
3. You'll see a trace tree:

```
orchestrator
  └── event_monitor
        └── calendar.fetch_events_between
```

---

## How it works

### Startup

`src/main.py` calls `configure_tracing()` which sets LangSmith env vars.

### Agent decorator

All agents use `@trace_agent("agent_name")` from `src/langchain_core/observability.py`:

```python
from src.langchain_core.observability import trace_agent

@trace_agent("gift_recommender")
def handle_gift_request(request):
    ...
```

This provides:
- **LangSmith traces** when `LANGCHAIN_TRACING_V2=true`
- **Local logs** always (`agent.start`, `agent.success`, `agent.error`)
- **Slack metadata** attached (user_id, channel_id) when context is passed

### Tool decorator

```python
from src.langchain_core.observability import trace_tool

@trace_tool("chroma.query_profiles")
def query_profiles(name: str):
    ...
```

### Future LangChain / LangGraph agents

When you add ReAct or LangGraph agents, LangSmith tracing is **automatic** — no extra code needed as long as env vars are set. LLM calls, tool calls, and graph nodes all appear as nested runs.

Use `get_chat_model()` from `src/langchain_core/llm.py` for consistent model setup.

---

## Local logging (always on)

Even without LangSmith, agents log to the terminal:

```
2026-06-28 10:00:01 INFO [gift_assistant.agents] agent.start
2026-06-28 10:00:02 INFO [gift_assistant.agents] agent.success
```

Set verbosity:
```env
LOG_LEVEL=DEBUG
```

---

## Disabling tracing

```env
LANGCHAIN_TRACING_V2=false
```

Local logging still works; LangSmith calls are skipped.

---

## Alternatives to LangSmith

| Tool | Notes |
|------|-------|
| **LangSmith** | Best fit — native LangChain/LangGraph integration |
| **Langfuse** | Open-source, self-hostable, LangChain integration |
| **Arize Phoenix** | Open-source tracing for LLM apps |
| **OpenTelemetry** | Generic — more setup, works with any stack |

We use LangSmith because you're adopting LangChain + LangGraph. The `@trace_agent` decorator uses LangSmith's `@traceable` under the hood.

---

## Adding tracing to a new agent

1. Import the decorator:
   ```python
   from src.langchain_core.observability import trace_agent
   ```

2. Decorate the handler:
   ```python
   @trace_agent("profile_collector")
   def handle_profile_message(message, context):
       ...
   ```

3. Add to `config/langchain.yaml` under `agents:` for documentation.

4. Traces appear automatically in LangSmith.

---

## Troubleshooting

### No traces in LangSmith
- Confirm `LANGCHAIN_TRACING_V2=true`
- Confirm `LANGCHAIN_API_KEY` is set and valid
- Restart the bot after changing `.env`
- Check terminal for `LangSmith tracing enabled`

### Traces appear but empty
- Agent may be returning before calling tools — check trace inputs/outputs in LangSmith UI

### `ModuleNotFoundError: langsmith`
```bash
pip install -r requirements.txt
```
