from unittest.mock import MagicMock, patch

from io import BytesIO

from PIL import Image

from src.agents.subagents.ecard_generator.backgrounds import (
    _image_from_response_item,
    _normalize_model,
    _normalize_quality,
    _normalize_size,
    build_background_prompt,
    generate_backgrounds_for_variants,
    get_background_provider,
    is_dalle_enabled,
    load_background,
)
from src.langchain_core.settings import get_ecard_image_settings
from src.agents.subagents.ecard_generator.parsing import fallback_ecard_variants
from src.agents.subagents.ecard_generator.render import render_card_jpeg


def test_legacy_model_mapping():
    assert _normalize_model("dall-e-3") == "gpt-image-1-mini"
    assert _normalize_size("1024x1792", "gpt-image-1-mini") == "1024x1536"
    assert _normalize_quality("standard", "gpt-image-1-mini") == "medium"
    assert _normalize_quality("hd", "gpt-image-1-mini") == "high"


def test_image_from_b64_response():
    buf = BytesIO()
    Image.new("RGB", (64, 64), (120, 80, 200)).save(buf, format="PNG")
    import base64

    item = type("Item", (), {"b64_json": base64.b64encode(buf.getvalue()).decode(), "url": None})()
    img = _image_from_response_item(item)
    assert img.size == (64, 64)


def test_build_background_prompt_no_text():
    prompt = build_background_prompt(
        "heartfelt",
        recipient="Mom",
        occasion="birthday",
        visual_hints=["pink", "floral"],
    )
    assert "Mom" in prompt
    assert "birthday" in prompt
    assert "No text" in prompt
    assert "pink" in prompt


def test_default_provider_is_pillow(monkeypatch):
    monkeypatch.delenv("ECARD_BACKGROUND_PROVIDER", raising=False)
    monkeypatch.delenv("ECARD_DALLE_ENABLED", raising=False)
    from src.langchain_core.settings import load_settings

    load_settings.cache_clear()
    settings = get_ecard_image_settings()
    assert settings["provider"] == "pillow"
    assert settings["enabled"] is False


def test_openai_provider_via_env(monkeypatch):
    monkeypatch.setenv("ECARD_BACKGROUND_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = get_ecard_image_settings()
    assert settings["provider"] == "openai"
    assert is_dalle_enabled() is True


@patch.dict("os.environ", {"OPENAI_API_KEY": "", "ECARD_BACKGROUND_PROVIDER": "pillow"})
def test_dalle_disabled_with_pillow_provider():
    assert get_background_provider() == "pillow"
    assert is_dalle_enabled() is False


@patch.dict(
    "os.environ",
    {
        "OPENAI_API_KEY": "sk-test",
        "ECARD_DALLE_ENABLED": "true",
    },
    clear=False,
)
def test_legacy_dalle_enabled_flag(monkeypatch):
    monkeypatch.delenv("ECARD_BACKGROUND_PROVIDER", raising=False)
    from src.langchain_core.settings import load_settings

    load_settings.cache_clear()
    assert get_ecard_image_settings()["provider"] == "openai"
    assert is_dalle_enabled() is True


def test_render_with_photo_background(tmp_path):
    card = fallback_ecard_variants("Mom", "birthday")[0]
    bg = Image.new("RGB", (1024, 1792), (200, 120, 160))
    data = render_card_jpeg(
        card,
        recipient="Mom",
        occasion="birthday",
        backgrounds={"heartfelt": bg},
    )
    assert data[:2] == b"\xff\xd8"
    assert len(data) > 8000


@patch("src.agents.subagents.ecard_generator.backgrounds.generate_background_image")
def test_generate_backgrounds_caches(mock_gen, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ECARD_BACKGROUND_PROVIDER", "openai")
    monkeypatch.setenv("ECARD_BACKGROUND_DIR", str(tmp_path))

    mock_gen.return_value = Image.new("RGB", (512, 512), (100, 150, 200))
    variants = fallback_ecard_variants("Mom", "birthday")

    paths = generate_backgrounds_for_variants(
        variants,
        user_id="U1",
        recipient="Mom",
        occasion="birthday",
        visual_hints=[],
        iteration=1,
    )

    assert len(paths) == 3
    for path in paths.values():
        assert load_background(path) is not None
    assert mock_gen.call_count == 3

    mock_gen.reset_mock()
    cached = generate_backgrounds_for_variants(
        variants,
        user_id="U1",
        recipient="Mom",
        occasion="birthday",
        visual_hints=[],
        iteration=1,
    )
    assert cached == paths
    mock_gen.assert_not_called()
