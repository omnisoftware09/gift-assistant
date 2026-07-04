from slack_sdk import WebClient

from src.shared.ssl_utils import get_ssl_context


def create_web_client(bot_token: str) -> WebClient:
    return WebClient(token=bot_token, ssl=get_ssl_context())
