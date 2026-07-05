from src.interfaces.slack.formatters.responses import format_response
from src.shared.conversation_context import AgentResponse


def test_gift_response_disables_link_unfurling():
    response = AgentResponse(
        text="Gift ideas",
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}],
        unfurl_links=False,
        unfurl_media=False,
    )
    kwargs = format_response(response)
    assert kwargs["unfurl_links"] is False
    assert kwargs["unfurl_media"] is False
