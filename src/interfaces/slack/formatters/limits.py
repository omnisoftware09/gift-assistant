"""Slack Block Kit size limits and helpers."""

SLACK_SECTION_TEXT_MAX = 3000
SLACK_CONTEXT_TEXT_MAX = 3000
SLACK_HEADER_TEXT_MAX = 150


def truncate_slack_text(text: str, max_len: int = SLACK_SECTION_TEXT_MAX) -> str:
    """Trim text to Slack's mrkdwn/plain_text limits."""
    if not text or len(text) <= max_len:
        return text or ""
    return text[: max_len - 1].rstrip() + "…"
