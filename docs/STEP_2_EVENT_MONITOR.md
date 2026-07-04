# Step 2: Event Monitoring Agent + Google Calendar

Documentation of what was built in Step 2 and how to use it.

---

## Goal

Allow users to ask in Slack about calendar events:

- `what events today?`
- `show my calendar tomorrow`
- `/events`
- `/events this week`

---

## Architecture decision: API vs MCP

We evaluated **Google MCP** and chose the **Google Calendar API** instead.

```
Slack message
    → orchestrator (detects event intent)
    → Event Monitoring Agent
    → tools/calendar/read_events.py
    → Google Calendar API
    → formatted Slack reply
```

**Google MCP** is designed for Cursor/IDE agents during development. It does not run inside your Slack bot process and cannot serve as the production calendar backend. The Calendar API with stored OAuth tokens is the correct approach for a always-on bot.

---

## Files added

```
gift-assistant/
├── scripts/
│   └── auth_google_calendar.py       # One-time OAuth → data/google_token.json
├── src/
│   ├── tools/calendar/
│   │   ├── client.py                 # Credentials + Calendar service
│   │   └── read_events.py            # fetch_events_for_day, fetch_upcoming_events
│   ├── agents/subagents/event_monitor/
│   │   ├── agent.py                  # handle_event_query()
│   │   └── parser.py                 # parse today/tomorrow/week queries
│   └── storage/models/
│       └── calendar_event.py         # CalendarEvent dataclass
├── tests/
│   └── test_event_parser.py
└── docs/
    └── GOOGLE_CALENDAR_SETUP.md      # OAuth setup guide
```

---

## Files modified

| File | Change |
|------|--------|
| `src/agents/orchestrator/agent.py` | Routes event queries to Event Monitoring Agent |
| `requirements.txt` | Added Google Calendar API libraries |
| `.env.example` | Added `GOOGLE_*` variables |
| `.gitignore` | Ignores `credentials.json`, `data/google_token.json` |

---

## Setup checklist

- [ ] Enable Google Calendar API in Google Cloud Console
- [ ] Create OAuth **Desktop app** credentials → `credentials.json`
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `python scripts/auth_google_calendar.py`
- [ ] Restart Slack bot: `python -m src.main`
- [ ] Test: `/events` or `what events today?`

Full details: [GOOGLE_CALENDAR_SETUP.md](GOOGLE_CALENDAR_SETUP.md)

---

## Supported queries

| User says | Behavior |
|-----------|----------|
| `what events today?` | Events for today |
| `calendar tomorrow` | Events for tomorrow |
| `upcoming events` / `/events` | Next 7 days |
| `events on Friday` | Events for next Friday |
| `this week` | Next 7 days |

---

## Example Slack response

```
Here are your events for the next 7 days:
• Sarah's birthday — All day
• Team standup — 9:00 AM
```

With Block Kit formatting in Slack.

---

## What's next (Step 3)

Proactive notifications:

> "Sarah's birthday is approaching. Do you want me to search gifts for her?"

This will use:
- `fetch_upcoming_events()` (already built)
- A background worker posting to Slack
- Block Kit buttons → Gift Recommender

---

## Commands reference

```bash
# Authorize Google Calendar (one time)
python scripts/auth_google_calendar.py

# Run Slack bot
python -m src.main

# Run tests
python -m pytest tests/test_event_parser.py -v
```
