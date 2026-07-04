#!/usr/bin/env python3
"""One-time Google Calendar OAuth setup. Saves token to data/google_token.json."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CLIENT_SECRETS = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "data/google_token.json")
PORT = int(os.getenv("GOOGLE_OAUTH_PORT", "8080"))

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def _load_oauth_config(secrets_path: Path) -> dict:
    """Support both Desktop (installed) and Web OAuth JSON files."""
    config = json.loads(secrets_path.read_text())
    if "installed" not in config and "web" in config:
        config["installed"] = config["web"]
    if "installed" not in config:
        raise SystemExit(
            "credentials.json must contain 'installed' or 'web' OAuth client config."
        )
    return config


def main() -> None:
    secrets_path = Path(CLIENT_SECRETS)
    if not secrets_path.exists():
        print(f"Missing {CLIENT_SECRETS}")
        print("\nOptions:")
        print("  1. Download Desktop OAuth JSON from Google Cloud Console")
        print("  2. Copy credentials.json from your testagent project:")
        print("     cp ../testagent/credentials.json .")
        print("\nSee docs/GOOGLE_CALENDAR_SETUP.md")
        raise SystemExit(1)

    token_path = Path(TOKEN_FILE)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    config = _load_oauth_config(secrets_path)
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    print(f"Opening browser for Google sign-in (localhost:{PORT})...")
    print("If browser fails, add this redirect URI in Google Cloud Console:")
    print(f"  http://localhost:{PORT}/")
    creds = flow.run_local_server(port=PORT, open_browser=True)

    token_path.write_text(json.dumps(json.loads(creds.to_json()), indent=2))
    print(f"\nSaved Google Calendar token to {token_path}")
    print("Restart the Slack bot and try: /events or /check-alerts")


if __name__ == "__main__":
    main()
