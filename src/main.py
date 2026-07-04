import logging
import os
import sys

from dotenv import load_dotenv

from src.interfaces.slack.app import create_slack_app, start_socket_mode
from src.langchain_core.tracing import configure_tracing
from src.workers.scheduler import start_proactive_worker


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    load_dotenv()
    _configure_logging()
    configure_tracing()

    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")

    if not bot_token or not app_token:
        print("Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN in .env")
        print("See README.md for Slack app setup instructions.")
        sys.exit(1)

    app = create_slack_app(bot_token)
    start_proactive_worker(app.client)
    start_socket_mode(app, app_token)


if __name__ == "__main__":
    main()
