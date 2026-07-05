from unittest.mock import MagicMock, patch

from src.agents.orchestrator.agent import handle_message
from src.agents.subagents.event_monitor.parser import is_event_query
from src.shared.conversation_context import AgentResponse, SlackContext
from src.shared.gift_session_store import GiftSession


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


@patch("src.agents.orchestrator.agent.start_gift_session")
@patch("src.agents.orchestrator.agent.load_recipient_context")
@patch("src.agents.orchestrator.agent.get_gift_session_store")
def test_new_gift_recipient_clears_stale_session(mock_store_fn, mock_load_ctx, mock_start):
    store = MagicMock()
    mock_store_fn.return_value = store
    store.get.return_value = GiftSession(
        user_id="U1",
        recipient="Alex",
        occasion="birthday",
        iteration=1,
        feedback=[],
        last_ranked=[{"title": "Old gift"}],
    )
    mock_load_ctx.return_value = MagicMock(name="Mom", age_range=None, past_gifts=[])
    mock_start.return_value = AgentResponse(text="Gift ideas for Mom")

    ctx = SlackContext(user_id="U1", channel_id="C1", thread_ts=None, team_id="T1")
    response = handle_message("recommend gift for Mom birthday", ctx)

    store.clear.assert_called_once_with("U1")
    mock_load_ctx.assert_called_once_with("Mom")
    mock_start.assert_called_once()
    assert response.text == "Gift ideas for Mom"
    assert mock_start.call_args[0][0].recipient == "Mom"


@patch("src.agents.orchestrator.agent.handle_active_gift_session")
@patch("src.agents.orchestrator.agent.get_gift_session_store")
def test_same_recipient_keeps_active_session(mock_store_fn, mock_handle_session):
    store = MagicMock()
    mock_store_fn.return_value = store
    session = GiftSession(
        user_id="U1",
        recipient="Sarah",
        occasion="graduation",
        iteration=1,
        feedback=[],
        last_ranked=[],
    )
    store.get.return_value = session
    mock_handle_session.return_value = AgentResponse(text="refined")

    ctx = SlackContext(user_id="U1", channel_id="C1", thread_ts=None, team_id="T1")
    response = handle_message("something more trendy", ctx)

    mock_handle_session.assert_called_once_with("something more trendy", session, ctx)
    store.clear.assert_not_called()
    assert response.text == "refined"
