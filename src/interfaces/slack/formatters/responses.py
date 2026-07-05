from src.shared.conversation_context import AgentResponse


def format_response(response: AgentResponse) -> dict:
    """Convert an AgentResponse into Slack message kwargs."""
    kwargs = {"text": response.text}
    if response.blocks:
        kwargs["blocks"] = response.blocks
    return kwargs


def welcome_blocks() -> list:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Gift Assistant"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "I can help you with:\n"
                    "• *Gift ideas* — `/gift Mom birthday`\n"
                    "• *Upcoming events* — `/events`\n"
                    "• *Recipient profiles* — tell me what someone likes\n"
                    "• *eCards* — visual greeting cards you can download for WhatsApp"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "DM me anytime or @mention me in a channel.",
                }
            ],
        },
    ]
