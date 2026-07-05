from unittest.mock import patch

from src.agents.orchestrator.agent import handle_message
from src.agents.subagents.event_monitor.parser import is_event_query
from src.shared.conversation_context import AgentResponse, SlackContext


def test_ecard_message_not_treated_as_event():
    msg = "create a greeting card for Mom for her birthday"
    assert not is_event_query(msg)


@patch("src.agents.orchestrator.agent.start_ecard_session")
def test_orchestrator_routes_ecard_before_events(mock_start_ecard):
    mock_start_ecard.return_value = AgentResponse(text="ecard draft")
    ctx = SlackContext(user_id="U1", channel_id="C1", thread_ts=None, team_id="T1")
    msg = "create a greeting card for Mom for her birthday"

    response = handle_message(msg, ctx)

    mock_start_ecard.assert_called_once_with(msg, ctx)
    assert response.text == "ecard draft"
