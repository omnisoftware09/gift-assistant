# Step 3: Proactive Event Alerts + Gift Search Buttons

Documentation of Step 3 — the bot reaches out to you in Slack when a gift-relevant calendar event is approaching.

---

## Goal

Two interaction patterns now work:

| Pattern | Example |
|---------|---------|
| **User asks** | `recommend gift for Sarah's graduation` |
| **Bot initiates** | `Sarah's birthday is coming up in 3 days. Do you want me to search for gift ideas?` |

With buttons: **Yes, search gifts** | **Remind me later** | **Skip**

---

## Architecture

```
Background worker (every 6h)
    → fetch upcoming calendar events (7 days)
    → filter gift-relevant (birthday, graduation, etc.)
    → skip already-notified events
    → DM user via Slack with Block Kit buttons

User clicks "Yes, search gifts"
    → action handler
    → Gift Recommender sub-agent
    → reply in thread
```

---

## Files added

```
src/
├── agents/subagents/event_monitor/
│   └── event_parser.py              # Parse "Sarah's birthday" from event titles
├── interfaces/slack/
│   ├── client.py                    # Shared WebClient factory
│   ├── formatters/alert_blocks.py   # Proactive alert + buttons
│   └── handlers/actions.py          # Button click handlers
├── workers/
│   ├── event_monitor_job.py         # Check calendar + send DMs
│   └── scheduler.py                 # Background thread in main.py
└── shared/
    └── notification_store.py        # Avoid duplicate alerts

scripts/
└── run_proactive_check.py           # Manual/cron trigger

tests/
└── test_proactive_alerts.py
```

---

## Files modified

| File | Change |
|------|--------|
| `src/main.py` | Starts proactive worker thread on boot |
| `src/interfaces/slack/app.py` | Registers action handlers |
| `src/interfaces/slack/handlers/slash_commands.py` | Added `/check-alerts` |
| `src/storage/models/calendar_event.py` | Added `id`, `days_until()`, `when_label()` |
| `.env.example` | Added proactive alert settings |

---

## Setup steps

### 1. Add Slack user ID to `.env`

Find your Slack member ID:
1. Open Slack → click your profile picture → **Profile**
2. Click **⋮** (more) → **Copy member ID**
3. Add to `.env`:

```env
SLACK_ALERT_USER_ID=U0123456789
PROACTIVE_ALERTS_ENABLED=true
PROACTIVE_ALERT_DAYS=7
PROACTIVE_CHECK_INTERVAL_HOURS=6
```

### 2. Add `/check-alerts` slash command in Slack app

1. [api.slack.com/apps](https://api.slack.com/apps) → your app
2. **Features → Slash Commands → Create New Command**
   - Command: `/check-alerts`
   - Description: `Check for approaching event alerts`
3. Reinstall app to workspace if prompted

> **Interactivity:** Socket Mode handles button clicks automatically — no Request URL needed.

### 3. Add a test event to Google Calendar

Create an all-day event like:
- **Sarah's birthday** — set date within the next 7 days

### 4. Restart the bot

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
source venv/bin/activate
python -m src.main
```

You should see:
```
Proactive alert worker started (every 6.0h)
Gift Assistant is running (Socket Mode)
```

### 5. Test manually

In Slack, run:
```
/check-alerts
```

You should receive a DM from the bot:
> *Sarah's birthday* is coming up in 3 days (Monday, June 30).
> Do you want me to search for gift ideas?
> [Yes, search gifts] [Remind me later] [Skip]

Click **Yes, search gifts** → Gift Recommender responds in the thread.

---

## Button actions

| Button | Behavior |
|--------|----------|
| **Yes, search gifts** | Routes to Gift Recommender with parsed recipient + occasion |
| **Remind me later** | Snoozes alert for 1 day |
| **Skip** | Never alerts for this event again |

State is stored in `data/notified_events.json` (gitignored).

---

## Gift-relevant event detection

Events are alert-worthy if the title contains occasions like:
- birthday, anniversary, graduation, wedding
- baby shower, retirement, housewarming, promotion, christmas

And a recipient is parsed from titles like:
- `Sarah's birthday`
- `Sarah graduation`
- `Mom birthday`

---

## Running alerts on a schedule

**Option A — built-in worker (default)**

Runs automatically when the bot is running. Checks every `PROACTIVE_CHECK_INTERVAL_HOURS` (default 6).

**Option B — cron (bot not always running)**

```bash
# crontab -e
0 9 * * * cd /Users/wadhwa09/aiprojects/gift-assistant && ./venv/bin/python scripts/run_proactive_check.py
```

**Option C — manual**

```bash
python scripts/run_proactive_check.py
# or in Slack: /check-alerts
```

---

## Disable proactive alerts

```env
PROACTIVE_ALERTS_ENABLED=false
```

---

## Troubleshooting

### No alerts sent
- Confirm `SLACK_ALERT_USER_ID` is set correctly
- Confirm Google Calendar is connected (`python scripts/auth_google_calendar.py`)
- Event title must match gift patterns (e.g. `Sarah's birthday`)
- Event must be within `PROACTIVE_ALERT_DAYS` (default 7)
- Alert may have already been sent — delete `data/notified_events.json` to reset

### Buttons don't respond
- Restart the bot after code changes
- Confirm Socket Mode is enabled
- Check bot logs for action handler errors

### DM not received
- Bot needs `im:write` scope (already in setup guide)
- User must have previously DM'd the bot at least once, or bot opens DM via `conversations_open`

---

## What's next

- Profile Collector + vector DB for smarter gift recommendations
- Gift Recommender: real product search, evaluate, rank
- eCard Generator Agent
