#!/usr/bin/env python3
"""Manually run proactive calendar alerts (for cron or testing)."""

import os
import sys

from dotenv import load_dotenv

from src.interfaces.slack.client import create_web_client
from src.workers.event_monitor_job import run_proactive_check

load_dotenv()


def main() -> None:
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    user_id = os.getenv("SLACK_ALERT_USER_ID")

    if not bot_token:
        print("Missing SLACK_BOT_TOKEN in .env")
        sys.exit(1)
    if not user_id:
        print("Missing SLACK_ALERT_USER_ID in .env")
        sys.exit(1)

    client = create_web_client(bot_token)
    result = run_proactive_check(client, user_id)
    print(result.get("message", f"Sent {result['sent']} alert(s)."))


if __name__ == "__main__":
    main()
