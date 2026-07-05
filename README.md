# Gift Assistant

A Slack-based gift assistant with a central orchestrator and specialized sub-agents.

## Quick start

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Slack tokens (see docs/SLACK_APP_SETUP.md)
python -m src.main
```

## Slack app setup

**Full step-by-step guide:** [docs/SLACK_APP_SETUP.md](docs/SLACK_APP_SETUP.md)

That guide covers:
- Creating the Slack app at api.slack.com
- Enabling Socket Mode
- Adding bot scopes and events
- Creating `/gift` and `/events` slash commands
- Installing to your workspace
- Testing DMs, @mentions, and slash commands
- Troubleshooting common issues

## What you need on your laptop

| Item | Required? |
|------|-----------|
| Python 3.10+ | Yes |
| `pip install -r requirements.txt` | Yes |
| Slack app tokens in `.env` | Yes |
| Slack desktop/web app | Recommended for testing |
| Slack server installed locally | **No** — Slack is cloud-hosted |
| Public URL / ngrok | **No** — uses Socket Mode |

## Google Calendar setup

**Full guide:** [docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md)

```bash
# One-time: place credentials.json in project root, then:
python scripts/auth_google_calendar.py
```

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/SLACK_APP_SETUP.md](docs/SLACK_APP_SETUP.md) | Create and connect Slack app |
| [docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md) | Google Calendar OAuth |
| [docs/STEP_2_EVENT_MONITOR.md](docs/STEP_2_EVENT_MONITOR.md) | Step 2 — Event Monitoring + Calendar |
| [docs/STEP_3_PROACTIVE_ALERTS.md](docs/STEP_3_PROACTIVE_ALERTS.md) | Step 3 — Proactive alerts + buttons |
| [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) | LangSmith tracing for all agents |
| [docs/LLM_AND_PROFILES.md](docs/LLM_AND_PROFILES.md) | LLM providers, ChromaDB, chunking |
| [docs/PROFILE_INGESTION.md](docs/PROFILE_INGESTION.md) | Import profiles from files + Slack |

## Test the bot

1. DM **Gift Assistant**: `Hello`
2. Gift query: `recommend gift for Sarah's graduation` (uses profile + LangGraph)
3. Events: `/events` or `what events today?`
4. Proactive alerts: `/check-alerts` (DMs you about approaching birthdays)
5. Slash commands: `/gift Mom birthday`
6. **Profile import:** `python scripts/import_profiles.py` then `What does Sarah like?`
7. **Slack import:** DM `import profiles` or `/import-profiles`
8. **eCard:** `create a greeting card for Mom for her birthday` or `/ecard Mom birthday`

## Project structure

```
gift-assistant/
├── config/
│   ├── agents.yaml
│   ├── slack.yaml
│   └── integrations.yaml
├── docs/
│   └── SLACK_APP_SETUP.md      # Detailed Slack setup guide
├── src/
│   ├── main.py                 # Entry point
│   ├── interfaces/slack/
│   │   ├── app.py              # Bolt app + Socket Mode
│   │   ├── handlers/
│   │   │   ├── messages.py     # DMs + @mentions
│   │   │   └── slash_commands.py
│   │   └── formatters/
│   │       └── responses.py    # Block Kit formatting
│   ├── agents/
│   │   ├── orchestrator/
│   │   └── subagents/
│   │       ├── gift_recommender/
│   │       └── event_monitor/
│   ├── tools/calendar/         # Google Calendar API
│   └── shared/
├── scripts/
│   └── auth_google_calendar.py
├── docs/
│   ├── SLACK_APP_SETUP.md
│   ├── GOOGLE_CALENDAR_SETUP.md
│   └── STEP_2_EVENT_MONITOR.md
├── .env.example
└── requirements.txt
```

## LLM providers & profiles

Swap LLM via `.env` — OpenAI, Anthropic, or **Ollama** (local).  
Profiles stored in **ChromaDB** with 1–2 sentence chunks + timestamps.

See [docs/LLM_AND_PROFILES.md](docs/LLM_AND_PROFILES.md).

```env
LLM_PROVIDER=openai          # or anthropic | ollama
EMBEDDING_MODEL=text-embedding-3-small
CHUNK_MIN_SENTENCES=1
CHUNK_MAX_SENTENCES=2
```

## Gift Recommender

LangGraph pipeline: **search** (LLM gift ideas) → **evaluate** (score vs profile) → **rank** (top 3).

Uses Chroma profiles when available. Swap LLM via `LLM_PROVIDER` (openai / ollama / anthropic).

## eCard Generator

Visual draft → refine → download loop with **DALL-E background art**:

1. `create a greeting card for Mom for her birthday`
2. Bot generates DALL-E backgrounds + text, attaches a **preview JPEG**
3. Reply *1*, *2*, or *3* → full-size **GIF or JPEG** uploaded to Slack (tap to download → WhatsApp)
4. Refine with feedback (e.g. *more pink*, *new background*, *floral*)

Requires **`OPENAI_API_KEY`**, Slack scope **`files:write`**. Set `ECARD_DALLE_ENABLED=false` to use gradient backgrounds only.

```env
ECARD_DALLE_ENABLED=true
ECARD_DALLE_MODEL=gpt-image-1-mini   # or gpt-image-1, gpt-image-1.5, gpt-image-2
ECARD_DALLE_SIZE=1024x1536
ECARD_DALLE_QUALITY=medium           # low | medium | high
```

Note: OpenAI retired `dall-e-3` in May 2026. Legacy `ECARD_DALLE_*` env vars now target GPT Image models.

## Next steps

- Product/web search API in the search node (optional)

