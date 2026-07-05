from src.agents.subagents.ecard_generator.session import parse_pick_phase_reply, parse_refine_phase_reply


def test_pick_phase_select_number():
    action, index, trailing = parse_pick_phase_reply("2")
    assert action == "select"
    assert index == 1
    assert trailing is None


def test_pick_phase_combined_design_feedback():
    action, index, trailing = parse_pick_phase_reply(
        "In design 2, add a cartoon girl with grad cap"
    )
    assert action == "select"
    assert index == 1
    assert "cartoon girl" in (trailing or "")


def test_pick_phase_rejects_freeform_feedback():
    action, _, _ = parse_pick_phase_reply("add more flowers")
    assert action == "invalid"


def test_refine_phase_finalize():
    action, index, feedback = parse_refine_phase_reply("finalize")
    assert action == "finalize"
    assert index is None


def test_refine_phase_feedback():
    action, index, feedback = parse_refine_phase_reply("add a cartoon girl with grad cap")
    assert action == "feedback"
    assert "cartoon girl" in feedback


def test_refine_phase_switch_design():
    action, index, _ = parse_refine_phase_reply("pick 1")
    assert action == "switch"
    assert index == 0


def test_gift_feedback_with_something_not_greeting():
    """Regression: 'something' contains 'hi' — must not trigger welcome during gift session."""
    from unittest.mock import MagicMock, patch

    from src.agents.orchestrator.agent import handle_message
    from src.shared.conversation_context import SlackContext
    from src.shared.gift_session_store import GiftSession

    msg = "Gift for Sarah for her birthday but something in trend these days"
    ctx = SlackContext(user_id="U1", channel_id="C1", thread_ts=None, team_id="T1")
    session = GiftSession(
        user_id="U1",
        recipient="Sarah",
        occasion="birthday",
        last_ranked=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
    )

    with patch("src.agents.orchestrator.agent.get_gift_session_store") as mock_store:
        mock_store.return_value.get.return_value = session
        with patch("src.agents.orchestrator.agent.handle_active_gift_session") as mock_handle:
            mock_handle.return_value = MagicMock(text="refined gifts")
            handle_message(msg, ctx)
            mock_handle.assert_called_once_with(msg, session, ctx)
