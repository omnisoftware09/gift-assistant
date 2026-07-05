from slack_bolt import App

import os

from src.agents.orchestrator.agent import handle_message, handle_slash_command
from src.agents.subagents.profile_collector.import_handler import handle_slack_file_uploads
from src.interfaces.slack.file_upload import deliver_response
from src.interfaces.slack.formatters.responses import format_response
from src.shared.conversation_context import SlackContext

IGNORED_MESSAGE_SUBTYPES = {
    "message_changed",
    "message_deleted",
    "bot_message",
    "channel_join",
    "channel_leave",
    "me_message",
}


def register_message_handlers(app: App) -> None:
    @app.event("app_mention")
    def on_mention(event, say, client, logger):
        text = _strip_bot_mention(event.get("text", ""))
        context = _context_from_event(event)
        files = event.get("files") or []
        if files:
            _reply_files(say, logger, files, context, error_label="app_mention")
        if text:
            _reply(client, say, logger, text, context, error_label="app_mention")

    @app.event("message")
    def on_dm(event, say, client, logger):
        if event.get("bot_id"):
            return
        subtype = event.get("subtype")
        if subtype and subtype not in IGNORED_MESSAGE_SUBTYPES:
            return
        if event.get("channel_type") != "im":
            return

        context = _context_from_event(event)
        files = event.get("files") or []
        if files:
            _reply_files(say, logger, files, context, error_label="DM")

        text = (event.get("text") or "").strip()
        if text:
            _reply(client, say, logger, text, context, error_label="DM")


def _reply_files(say, logger, files, context, error_label):
    try:
        token = os.getenv("SLACK_BOT_TOKEN", "")
        response = handle_slack_file_uploads(files, token)
        say(**format_response(response), thread_ts=context.thread_ts)
    except Exception:
        logger.exception("Failed to handle file upload for %s", error_label)
        say(
            text="Sorry, I couldn't import that file.",
            thread_ts=context.thread_ts,
        )


def _reply(client, say, logger, text, context, error_label):
    try:
        response = handle_message(text, context)
        if response.files:
            deliver_response(
                client,
                context.channel_id,
                response,
                thread_ts=context.thread_ts,
            )
        else:
            say(**format_response(response), thread_ts=context.thread_ts)
    except Exception:
        logger.exception("Failed to handle %s", error_label)
        say(text="Sorry, something went wrong.", thread_ts=context.thread_ts)


def _context_from_event(event) -> SlackContext:
    return SlackContext(
        user_id=event["user"],
        channel_id=event["channel"],
        thread_ts=event.get("thread_ts") or event.get("ts"),
        team_id=event.get("team"),
    )


def _strip_bot_mention(text: str) -> str:
    return " ".join(part for part in text.split() if not part.startswith("<@")).strip()
