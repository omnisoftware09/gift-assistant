"""eCard Generator — ReAct fallback + draft/refine session flow."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.subagents.ecard_generator.flow import start_ecard_session
from src.agents.subagents.ecard_generator.parser import is_ecard_request, parse_ecard_request
from src.agents.subagents.ecard_generator.tools import ECARD_TOOLS
from src.langchain_core.llm import get_chat_model
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext

SYSTEM_PROMPT = """You are the eCard Generator for Gift Assistant.
Help users create personalized greeting cards.

Use tools when needed:
- get_recipient_profile_for_ecard: look up interests before writing
- get_recipient_ecard_history: avoid repeating past card messages

If the user gives recipient + occasion, suggest they say:
"create a greeting card for [name] for [occasion]"
Be concise."""


def _run_react_agent(message: str) -> str:
    from langgraph.prebuilt import create_react_agent

    model = get_chat_model()
    agent = create_react_agent(model, ECARD_TOOLS)
    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        }
    )
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)


@trace_agent("ecard_generator")
def handle_ecard_request(message: str, context: SlackContext | None = None) -> AgentResponse:
    parsed = parse_ecard_request(message)
    if parsed and parsed.get("recipient") and context:
        return start_ecard_session(message, context)

    if is_ecard_request(message):
        if not context:
            return AgentResponse(
                text="Try: *create a greeting card for Mom for her birthday*"
            )
        if parsed and not parsed.get("recipient"):
            return AgentResponse(
                text=(
                    "Who is the card for? Try:\n"
                    "*create a greeting card for Mom for her birthday*"
                )
            )

    try:
        reply = _run_react_agent(message)
        return AgentResponse(text=reply)
    except Exception as exc:
        return AgentResponse(
            text=(
                f"I couldn't process that eCard request ({exc}).\n"
                "Try: *create a greeting card for Sarah for her graduation*"
            )
        )
