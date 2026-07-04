from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from src.interfaces.slack.handlers.actions import register_action_handlers
from src.interfaces.slack.handlers.messages import register_message_handlers
from src.interfaces.slack.handlers.slash_commands import register_slash_commands
from src.shared.ssl_utils import get_ssl_context


def create_slack_app(bot_token: str) -> App:
    ssl_context = get_ssl_context()
    client = WebClient(token=bot_token, ssl=ssl_context)
    app = App(client=client)
    register_message_handlers(app)
    register_slash_commands(app)
    register_action_handlers(app)
    return app


def start_socket_mode(app: App, app_token: str) -> None:
    handler = SocketModeHandler(app, app_token)
    print("Gift Assistant is running (Socket Mode)", flush=True)
    print("Open Slack and DM your bot, or try /gift and /events", flush=True)
    handler.start()
