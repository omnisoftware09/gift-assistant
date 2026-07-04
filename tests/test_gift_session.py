import tempfile
from pathlib import Path

from src.agents.orchestrator.gift_session import parse_gift_session_reply
from src.storage.gift_history.db import init_db
from src.storage.gift_history.store import GiftHistoryStore


def test_parse_session_replies():
    assert parse_gift_session_reply("done") == ("done", None)
    assert parse_gift_session_reply("2") == ("select", 1)
    assert parse_gift_session_reply("select 3") == ("select", 2)
    assert parse_gift_session_reply("more outdoors please") == ("feedback", None)


def test_gift_history_store():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        import os

        os.environ["GIFT_HISTORY_DB"] = str(db_path)
        init_db()
        store = GiftHistoryStore()

        store.set_age_range("Sarah", "30-35")
        store.save_selected_gift("Sarah", "Trail daypack", "outdoors", occasion="birthday")
        ctx = store.get_recipient_context("Sarah")

        assert ctx.age_range == "30-35"
        assert len(ctx.past_gifts) == 1
        assert ctx.past_gifts[0].title == "Trail daypack"
        assert "outdoors" in ctx.excluded_categories()
