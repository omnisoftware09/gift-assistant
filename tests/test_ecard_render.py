from src.agents.subagents.ecard_generator.parsing import fallback_ecard_variants
from src.agents.subagents.ecard_generator.render import (
    render_card_gif,
    render_card_jpeg,
    render_final_card,
    render_preview_sheet,
)
from src.agents.subagents.ecard_generator.visual_hints import extract_visual_hints, wants_animation


def test_render_jpeg():
    card = fallback_ecard_variants("Mom", "birthday")[0]
    data = render_card_jpeg(card, recipient="Mom", occasion="birthday")
    assert data[:2] == b"\xff\xd8"
    assert len(data) > 5000


def test_render_gif():
    card = fallback_ecard_variants("Mom", "birthday")[1]
    data = render_card_gif(card, recipient="Mom", occasion="birthday")
    assert data[:3] == b"GIF"
    assert len(data) > 5000


def test_render_preview_sheet():
    variants = fallback_ecard_variants("Sarah", "graduation")
    data = render_preview_sheet(variants, recipient="Sarah", occasion="graduation")
    assert data[:2] == b"\xff\xd8"
    assert len(data) > 8000


def test_render_final_card_formats():
    heartfelt = fallback_ecard_variants("Mom", "birthday")[0]
    funny = fallback_ecard_variants("Mom", "birthday")[1]
    formal = fallback_ecard_variants("Mom", "birthday")[2]

    assert render_final_card(heartfelt, recipient="Mom", occasion="birthday", visual_hints=[]).mime_type == "image/gif"
    assert render_final_card(funny, recipient="Mom", occasion="birthday", visual_hints=[]).mime_type == "image/gif"
    assert render_final_card(formal, recipient="Mom", occasion="birthday", visual_hints=[]).mime_type == "image/jpeg"


def test_visual_hints():
    hints = extract_visual_hints("make it more pink and floral")
    assert "pink" in hints
    assert "floral" in hints
    assert wants_animation(hints, "formal") is False
    assert wants_animation(["animate"], "formal") is True
    assert wants_animation(["static"], "funny") is False
