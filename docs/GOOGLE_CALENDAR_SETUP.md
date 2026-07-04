# Google Calendar Setup

Connect Gift Assistant to your Google Calendar so the Event Monitoring Agent can read birthdays, anniversaries, and other events.

## Why Google Calendar API (not Google MCP)?

| Approach | Use case |
|----------|----------|
| **Google Calendar API** (this project) | Your Slack bot runs 24/7 as a standalone Python app and needs persistent calendar access |
| **Google MCP server** | Cursor IDE agents during development — not suitable as the runtime backend for a Slack bot |

We use the **Calendar API directly** with OAuth tokens stored in `data/google_token.json`.

---

## Prerequisites

- Google account with a calendar
- Gift Assistant project at `/Users/wadhwa09/aiprojects/gift-assistant`

---

## Step 1 — Create Google Cloud project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (e.g. `gift-assistant`) or select an existing one

## Step 2 — Enable Google Calendar API

1. **APIs & Services → Library**
2. Search **Google Calendar API**
3. Click **Enable**

## Step 3 — Configure OAuth consent screen

1. **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in:
   - **App name:** `Gift Assistant`
   - **User support email:** your email
   - **Developer contact:** your email
4. **Scopes** → Add `.../auth/calendar.readonly` (See all your calendars)
5. **Test users** → Add your Google account email
6. Save

## Step 4 — Create OAuth credentials

1. **APIs & Services → Credentials**
2. **Create Credentials → OAuth client ID**
3. Application type: **Desktop app** (recommended)
4. Download JSON → save as `credentials.json` in the project root

> **Already have Web credentials from testagent?** Copy them in:
> ```bash
> cp ../testagent/credentials.json .
> ```
> Then add this **Authorized redirect URI** to the same OAuth client in Google Cloud Console:
> ```
> http://localhost:8080/
> ```

## Step 5 — Configure environment

Add to your `.env` (or use defaults):

```env
GOOGLE_CLIENT_SECRETS_FILE=credentials.json
GOOGLE_TOKEN_FILE=data/google_token.json
GOOGLE_OAUTH_PORT=8080
```

## Step 6 — Install dependencies

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
source venv/bin/activate
pip install -r requirements.txt
```

## Step 7 — Authorize calendar access (one time)

```bash
python scripts/auth_google_calendar.py
```

1. Browser opens → sign in with Google
2. Approve calendar read access
3. Token saved to `data/google_token.json`

## Step 8 — Test in Slack

With the bot running (`python -m src.main`), try:

```
/events
what events today?
show my calendar tomorrow
upcoming events
```

---

## Troubleshooting

### `Missing credentials.json`
Download OAuth client JSON from Google Cloud Console (Desktop app type).

### `redirect_uri_mismatch`
You created a **Web** client instead of **Desktop app**. Create a Desktop OAuth client.

### `Calendar not connected`
Run `python scripts/auth_google_calendar.py` again.

### Token expired
The client auto-refreshes if a refresh token exists. If not, re-run the auth script.

### Port 8080 in use
Set `GOOGLE_OAUTH_PORT=8081` in `.env` and run auth again.

---

## Security notes

- Never commit `credentials.json` or `data/google_token.json` (both are in `.gitignore`)
- Scope is **read-only** — the bot cannot modify your calendar yet
