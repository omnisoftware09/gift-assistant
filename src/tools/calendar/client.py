import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "data/google_token.json")

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


class CalendarNotConnectedError(Exception):
    """Raised when Google Calendar token is missing or invalid."""


def _token_path() -> Path:
    return Path(TOKEN_FILE)


def _secrets_path() -> Path:
    return Path(CLIENT_SECRETS_FILE)


def calendar_setup_hint() -> str:
    secrets = _secrets_path()
    token = _token_path()
    if not secrets.exists():
        return (
            f"Missing {CLIENT_SECRETS_FILE}. "
            "Copy it from Google Cloud Console — see docs/GOOGLE_CALENDAR_SETUP.md"
        )
    if not token.exists():
        return "Run: python scripts/auth_google_calendar.py"
    return "Run: python scripts/auth_google_calendar.py"


def get_credentials() -> Credentials:
    if not _secrets_path().exists():
        raise CalendarNotConnectedError(calendar_setup_hint())

    token_path = _token_path()
    if not token_path.exists():
        raise CalendarNotConnectedError(
            f"Google Calendar not connected. {calendar_setup_hint()}"
        )

    creds = Credentials.from_authorized_user_info(
        json.loads(token_path.read_text()), SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    if not creds.valid:
        raise CalendarNotConnectedError(
            "Google Calendar token expired. Run: python scripts/auth_google_calendar.py"
        )

    return creds


def get_calendar_service():
    return build("calendar", "v3", credentials=get_credentials())
