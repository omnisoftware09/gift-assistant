import tempfile
from pathlib import Path

from src.agents.subagents.ecard_generator.parsing import (
    fallback_ecard_variants,
    normalize_ecard_variants,
)
from src.agents.subagents.ecard_generator.parser import parse_ecard_request
from src.storage.gift_history.db import init_db
from src.storage.gift_history.store import GiftHistoryStore


def test_ecard_parse_slash():
    parsed = parse_ecard_request("Mom birthday", from_slash_command=True)
    assert parsed is not None
    assert parsed["recipient"] == "Mom"
    assert parsed["occasion"] == "birthday"


def test_normalize_ecard_variants():
    raw = [
        {
            "style": "heartfelt",
            "headline": "Happy Day",
            "message": "Wishing you joy.",
            "sign_off": "Love,",
        },
        {
            "style": "funny",
            "headline": "Ha!",
            "message": "You're old.",
            "sign_off": "Cheers,",
        },
    ]
    variants = normalize_ecard_variants(raw)
    assert len(variants) == 2
    assert variants[0]["style"] == "heartfelt"


def test_fallback_ecard_variants():
    variants = fallback_ecard_variants("Sarah", "graduation")
    assert len(variants) == 3
    styles = {v["style"] for v in variants}
    assert styles == {"heartfelt", "funny", "formal"}


def test_save_ecard_history():
    with tempfile.TemporaryDirectory() as tmp:
        import os

        os.environ["GIFT_HISTORY_DB"] = str(Path(tmp) / "test.db")
        init_db()
        store = GiftHistoryStore()
        store.save_ecard(
            "Mom",
            "heartfelt",
            "Happy Birthday!",
            "Hope your day is wonderful.",
            sign_off="Love,",
            occasion="birthday",
        )
        history = store.get_ecard_history("Mom")
        assert len(history) == 1
        assert history[0].headline == "Happy Birthday!"
