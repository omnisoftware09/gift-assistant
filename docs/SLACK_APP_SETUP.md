# Slack App Setup Guide

Step-by-step instructions to create and connect a Slack app for Gift Assistant.

**Time required:** ~15 minutes  
**Cost:** Free (Slack free tier works)

---

## Prerequisites

- A Slack workspace where you can install apps (create one at [slack.com](https://slack.com) if needed)
- Python 3.10+ installed on your laptop
- Gift Assistant project cloned at `/Users/wadhwa09/aiprojects/gift-assistant`

---

## Part 1: Install software on your laptop

You do **not** install Slack server software locally. Slack runs in the cloud. Your laptop runs the Gift Assistant bot, which connects to Slack over the internet.

### Step 1.1 — Install Python dependencies

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 1.2 — Install Slack desktop (optional but recommended)

Download from [slack.com/downloads](https://slack.com/downloads) so you can DM your bot and test slash commands.

---

## Part 2: Create the Slack app (browser)

### Step 2.1 — Create the app

1. Open [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. **App Name:** `Gift Assistant`
5. **Pick a workspace:** select your workspace
6. Click **Create App**

### Step 2.2 — Enable App Home Messages tab

This lets you **reply in DMs** to the bot (and removes "Sending messages to this app has been turned off").

1. Left sidebar → **Features** → **App Home**
2. Under **Show Tabs**, turn **Messages Tab** → **ON**
3. Check **Allow users to send Slash commands and messages from the messages tab**
4. Save changes

### Step 2.3 — Add a bot user (if prompted)

1. Under **Your App's Presence in Slack**, confirm a bot user exists
2. Display name: `Gift Assistant`

### Step 2.4 — Enable Socket Mode

Socket Mode lets your bot run on localhost without exposing a public URL.

1. Left sidebar → **Settings** → **Socket Mode**
2. Toggle **Enable Socket Mode** → **ON**
3. Click **Generate an app-level token**
4. Token name: `gift-assistant-socket`
5. Add scope: `connections:write`
6. Click **Generate**
7. **Copy the token** — it starts with `xapp-`
8. Save it somewhere safe (you'll put it in `.env` as `SLACK_APP_TOKEN`)

### Step 2.5 — Add bot token scopes

These permissions let the bot read DMs, respond, and handle mentions.

1. Left sidebar → **Features** → **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add each of these:

| Scope | Why it's needed |
|-------|-----------------|
| `app_mentions:read` | Read @mentions in channels |
| `chat:write` | Send messages |
| `commands` | Handle `/gift` and `/events` slash commands |
| `im:history` | Read DM history |
| `im:read` | Access DM channels |
| `im:write` | Open DM conversations |

### Step 2.6 — Enable Event Subscriptions

1. Left sidebar → **Features** → **Event Subscriptions**
2. Toggle **Enable Events** → **ON**
3. Under **Subscribe to bot events**, click **Add Bot User Event**
4. Add these events:

| Event | Why it's needed |
|-------|-----------------|
| `app_mention` | User @mentions the bot in a channel |
| `message.im` | User sends a direct message to the bot |

5. Click **Save Changes**

> Socket Mode is enabled, so you do **not** need to set a Request URL.

### Step 2.7 — Create slash commands

1. Left sidebar → **Features** → **Slash Commands**
2. Click **Create New Command**

**Command 1:**
- Command: `/gift`
- Request URL: leave blank (Socket Mode handles this)
- Short description: `Get gift recommendations`
- Usage hint: `[person] [occasion]`
- Save

**Command 2:**
- Command: `/events`
- Request URL: leave blank
- Short description: `Show upcoming calendar events`
- Usage hint: `[today|tomorrow]`
- Save

### Step 2.8 — Install the app to your workspace

1. Left sidebar → **Settings** → **Install App**
2. Click **Install to Workspace**
3. Review permissions → **Allow**
4. Copy the **Bot User OAuth Token** — it starts with `xoxb-`
5. Save it as `SLACK_BOT_TOKEN` in your `.env` file

### Step 2.9 — Invite the bot to a channel (for @mentions)

In Slack (not the API site):

1. Open a channel (e.g. `#general`)
2. Type: `/invite @Gift Assistant`
3. Press Enter

Now you can @mention the bot in that channel.

---

## Part 3: Configure Gift Assistant

### Step 3.1 — Create your `.env` file

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
cp .env.example .env
```

Edit `.env`:

```env
SLACK_BOT_TOKEN=xoxb-paste-your-bot-token-here
SLACK_APP_TOKEN=xapp-paste-your-app-token-here
```

> Never commit `.env` to git. It's already in `.gitignore`.

---

## Part 4: Run the bot

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
source venv/bin/activate
python -m src.main
```

Expected output:

```
Gift Assistant is running (Socket Mode)
Open Slack and DM your bot, or try /gift and /events
```

Leave this terminal running while you test.

---

## Part 5: Test in Slack

### Test 1 — Direct message

1. Open Slack
2. Click **Apps** in the left sidebar (or search for `Gift Assistant`)
3. Open a DM with **Gift Assistant**
4. Send: `Hello`

Expected: welcome message with help text and Block Kit layout.

### Test 2 — @mention in a channel

1. Go to a channel where you invited the bot
2. Type: `@Gift Assistant what gifts for Mom?`

Expected: bot replies in the channel thread.

### Test 3 — Slash commands

In any channel or DM:

```
/gift Mom birthday
/events
```

Expected: stub responses ("coming soon") confirming the command works.

---

## Troubleshooting

### `SSL: CERTIFICATE_VERIFY_FAILED` on macOS

This project uses the `certifi` CA bundle automatically. If you still see SSL errors:

```bash
pip install -r requirements.txt
```

Or run Apple's Python certificate installer once:

```bash
/Applications/Python\ 3.12/Install\ Certificates.command
```

(Adjust the version number to match your Python install.)

### "Sending messages to this app has been turned off"

You may see this in the DM input box when the bot messages you first. **The alert buttons still work** — click *Yes, search gifts* without typing.

To enable the message box so you can also type DMs:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → your **Gift Assistant** app
2. **Features → App Home**
3. Turn **Messages Tab** → **ON**
4. Check **Allow users to send Slash commands and messages from the messages tab**
5. **Save**
6. **Settings → Install App** → **Reinstall to Workspace** (if prompted)
7. Refresh Slack (or quit and reopen the app)

Then open the bot DM again — you should be able to type messages like `Hello`.

### Bot doesn't respond to DMs

- Confirm `message.im` is in Event Subscriptions
- Confirm `im:history` and `im:read` scopes are added
- Restart the bot (`Ctrl+C`, then `python -m src.main` again)
- Reinstall the app: **Install App** → reinstall to refresh scopes

### Bot doesn't respond to @mentions

- Invite the bot to the channel: `/invite @Gift Assistant`
- Confirm `app_mention` event is subscribed
- Confirm `app_mentions:read` scope is added

### Slash commands don't appear

- Confirm commands are created under **Slash Commands** in the app settings
- Confirm `commands` scope is added
- Reinstall the app after adding scopes
- Wait 1–2 minutes for Slack to propagate changes

### `Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN`

- Check `.env` exists in the project root
- Check tokens have no extra spaces or quotes
- Bot token starts with `xoxb-`, app token starts with `xapp-`

### `operation_not_supported` or Socket Mode errors

- Confirm Socket Mode is enabled in app settings
- Confirm `SLACK_APP_TOKEN` is the **app-level** token (not the bot token)

### Bot was working, stopped after scope changes

1. Stop the bot
2. In Slack API site → **Install App** → **Reinstall to Workspace**
3. Update `.env` if the bot token changed
4. Restart the bot

---

## Token reference

| Variable | Where to get it | Starts with |
|----------|-----------------|-------------|
| `SLACK_BOT_TOKEN` | OAuth & Permissions → Bot User OAuth Token | `xoxb-` |
| `SLACK_APP_TOKEN` | Settings → Socket Mode → App-Level Token | `xapp-` |

---

## What happens under the hood

```
You (Slack DM or @mention)
    ↓
Slack cloud
    ↓  (Socket Mode WebSocket)
src/interfaces/slack/handlers/
    ↓
src/agents/orchestrator/agent.py
    ↓
Reply formatted for Slack → back to you
```

No public URL or ngrok required — Socket Mode connects outbound from your laptop to Slack.

---

## Next steps

Once the bot responds in Slack, you're ready to build:

1. Event Monitoring Agent + Google Calendar
2. Profile Collector Agent + vector DB
3. Gift Recommender Agent
4. eCard Generator Agent
