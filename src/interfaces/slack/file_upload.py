"""Post AgentResponse messages and file attachments to Slack."""

import logging

from slack_sdk import WebClient

from src.interfaces.slack.formatters.responses import format_response
from src.shared.conversation_context import AgentResponse, SlackFile

logger = logging.getLogger("gift_assistant.slack")


def deliver_response(
    client: WebClient,
    channel_id: str,
    response: AgentResponse,
    *,
    thread_ts: str | None = None,
) -> None:
    """Post text/blocks then upload any attached files."""
    kwargs = format_response(response)
    kwargs["channel"] = channel_id
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    client.chat_postMessage(**kwargs)

    for slack_file in response.files:
        _upload_file(client, channel_id, slack_file, thread_ts=thread_ts)


def _upload_file(
    client: WebClient,
    channel_id: str,
    slack_file: SlackFile,
    *,
    thread_ts: str | None = None,
) -> None:
    try:
        upload_kwargs = {
            "channel": channel_id,
            "file": slack_file.data,
            "filename": slack_file.filename,
            "title": slack_file.title or slack_file.filename,
        }
        if thread_ts:
            upload_kwargs["thread_ts"] = thread_ts
        if slack_file.initial_comment:
            upload_kwargs["initial_comment"] = slack_file.initial_comment
        client.files_upload_v2(**upload_kwargs)
    except Exception:
        logger.exception("Failed to upload %s to Slack", slack_file.filename)
        raise
