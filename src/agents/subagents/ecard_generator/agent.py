"""eCard Generator sub-agent — ReAct + image/text generation (stub)."""

from src.agents.subagents.ecard_generator.parser import parse_ecard_request
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext


@trace_agent("ecard_generator")
def handle_ecard_request(message: str, context: SlackContext | None = None) -> AgentResponse:
    """Stub: real eCard generation (copy, layout, delivery) not implemented yet."""
    parsed = parse_ecard_request(message)
    if not parsed:
        return AgentResponse(
            text=(
                "eCard Generator (stub).\n"
                "Try: *create a greeting card for Mom for her birthday*"
            )
        )

    recipient = parsed.get("recipient") or "_recipient not specified_"
    occasion = parsed.get("occasion") or "_occasion not specified_"

    text = (
        f"*eCard Generator (stub)*\n\n"
        f"*Recipient:* {recipient}\n"
        f"*Occasion:* {occasion}\n\n"
        "Planned pipeline: draft message → pick style → generate card → send link.\n"
        "_ReAct agent with image/copy tools coming in the next step._"
    )

    return AgentResponse(text=text)
