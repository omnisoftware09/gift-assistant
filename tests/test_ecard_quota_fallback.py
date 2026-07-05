from unittest.mock import patch

from src.agents.subagents.ecard_generator.flow import _profile_chunks, start_ecard_session
from src.shared.conversation_context import SlackContext


@patch("src.agents.subagents.ecard_generator.flow.get_profile_store")
def test_profile_chunks_uses_semantic_query(mock_store):
    mock_store.return_value.query_profile.return_value = ["Likes hiking"]
    chunks = _profile_chunks("Sarah", "graduation")
    assert chunks == ["Likes hiking"]
    mock_store.return_value.query_profile.assert_called_once_with(
        "Sarah", query="greeting card message for Sarah graduation"
    )


@patch("src.agents.subagents.ecard_generator.flow._start_ecard_session_inner")
def test_start_ecard_quota_error_message(mock_inner):
    mock_inner.side_effect = Exception(
        "Error code: 429 - {'error': {'code': 'insufficient_quota'}}"
    )
    ctx = SlackContext(user_id="U1", channel_id="C1", thread_ts=None, team_id="T1")
    resp = start_ecard_session("create a greeting card for Mom for her birthday", ctx)
    assert "quota" in resp.text.lower()
    assert "pillow" in resp.text.lower()
