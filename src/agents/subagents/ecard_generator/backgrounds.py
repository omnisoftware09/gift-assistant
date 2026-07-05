"""Generate AI background art for eCards (OpenAI GPT Image models)."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from PIL import Image

from src.langchain_core.settings import get_ecard_image_settings

logger = logging.getLogger("gift_assistant.ecard_generator.backgrounds")


def _background_dir() -> Path:
    return Path(os.getenv("ECARD_BACKGROUND_DIR", "data/ecard_backgrounds"))

STYLE_PROMPTS = {
    "heartfelt": (
        "warm soft watercolor wash, gentle roses and golden light, "
        "romantic pastel tones, dreamy bokeh, elegant greeting card backdrop"
    ),
    "funny": (
        "playful bright confetti and balloons, cheerful party atmosphere, "
        "vivid colors, whimsical celebration scene, fun greeting card backdrop"
    ),
    "formal": (
        "sophisticated navy and cream abstract texture, subtle gold filigree, "
        "refined minimalist elegance, premium stationery backdrop"
    ),
}


# DALL-E 2/3 retired May 2026 — map legacy config to GPT Image models.
LEGACY_MODEL_MAP = {
    "dall-e-3": "gpt-image-1-mini",
    "dall-e-2": "gpt-image-1-mini",
}

GPT_IMAGE_MODELS = ("gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini")

QUALITY_MAP = {
    "standard": "medium",
    "hd": "high",
}

SIZE_MAP = {
    "1024x1792": "1024x1536",
    "1792x1024": "1536x1024",
}


def _normalize_model(model: str) -> str:
    model = model.strip().lower()
    return LEGACY_MODEL_MAP.get(model, model)


def _normalize_quality(quality: str, model: str) -> str | None:
    q = QUALITY_MAP.get(quality.lower(), quality.lower())
    if model.startswith("gpt-image"):
        if q in ("low", "medium", "high", "auto"):
            return q
        return "medium"
    if q in ("standard", "hd"):
        return q
    return None


def _normalize_size(size: str, model: str) -> str:
    mapped = SIZE_MAP.get(size, size)
    if model.startswith("gpt-image"):
        valid = {"1024x1024", "1024x1536", "1536x1024", "auto"}
        if mapped in valid:
            return mapped
        return "1024x1536"
    return mapped


def _fallback_models(primary: str) -> list[str]:
    chain = [_normalize_model(primary), *GPT_IMAGE_MODELS]
    seen: set[str] = set()
    ordered: list[str] = []
    for m in chain:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def is_dalle_enabled() -> bool:
    """True when OpenAI GPT Image backgrounds are active (provider=openai + API key)."""
    settings = get_ecard_image_settings()
    if settings["provider"] != "openai":
        return False
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_background_provider() -> str:
    return get_ecard_image_settings()["provider"]


def _cache_key(
    style: str,
    occasion: str | None,
    recipient: str,
    visual_hints: list[str],
    iteration: int,
    design_feedback: list[str] | None = None,
) -> str:
    raw = "|".join(
        [
            style,
            occasion or "",
            recipient,
            ",".join(sorted(visual_hints)),
            ",".join(sorted(design_feedback or [])),
            str(iteration),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_background_prompt(
    style: str,
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    design_feedback: list[str] | None = None,
) -> str:
    base = STYLE_PROMPTS.get(style, STYLE_PROMPTS["heartfelt"])
    occasion_line = (occasion or "celebration").replace("her ", "").replace("his ", "")
    extras: list[str] = []
    if visual_hints:
        extras.append(f"Visual preferences: {', '.join(visual_hints)}.")
    if design_feedback:
        extras.append(f"Required visual elements: {'; '.join(design_feedback)}.")
    extra_line = " ".join(extras)
    return (
        f"Vertical portrait greeting card background for {occasion_line} "
        f"for someone named {recipient}. {base}. {extra_line} "
        "Illustrated or cartoon characters are OK when requested. "
        "No text, no letters, no words, no watermark, no logos. "
        "Soft artistic illustration suitable for overlaying a message."
    )


def _download_image(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()
    return Image.open(BytesIO(data)).convert("RGB")


def _image_from_response_item(item) -> Image.Image:
    if getattr(item, "b64_json", None):
        raw = base64.b64decode(item.b64_json)
        return Image.open(BytesIO(raw)).convert("RGB")
    if getattr(item, "url", None):
        return _download_image(item.url)
    raise ValueError("Image response contained no b64_json or url")


def _call_images_api(client, *, model: str, prompt: str, size: str, quality: str | None):
    kwargs: dict = {"model": model, "prompt": prompt, "n": 1}
    if model.startswith("gpt-image"):
        kwargs["size"] = size
        if quality:
            kwargs["quality"] = quality
    else:
        kwargs["size"] = size
        if quality:
            kwargs["quality"] = quality
    return client.images.generate(**kwargs)


def generate_background_image(
    style: str,
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    design_feedback: list[str] | None = None,
) -> Image.Image | None:
    if not is_dalle_enabled():
        return None

    settings = get_ecard_image_settings()
    prompt = build_background_prompt(
        style,
        recipient=recipient,
        occasion=occasion,
        visual_hints=visual_hints,
        design_feedback=design_feedback,
    )

    try:
        from openai import BadRequestError, OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        last_error: Exception | None = None

        for model in _fallback_models(settings["model"]):
            size = _normalize_size(settings["size"], model)
            quality = _normalize_quality(settings["quality"], model)
            try:
                response = _call_images_api(
                    client,
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                )
                img = _image_from_response_item(response.data[0])
                logger.info(
                    "GPT Image background generated model=%s style=%s recipient=%s",
                    model,
                    style,
                    recipient,
                )
                return img
            except BadRequestError as exc:
                last_error = exc
                err = getattr(exc, "body", {}) or {}
                code = (err.get("error") or {}).get("code", "")
                if code in ("invalid_value", "model_not_found") or "does not exist" in str(exc):
                    logger.warning("Image model %s unavailable, trying fallback: %s", model, exc)
                    continue
                logger.exception("GPT Image background generation failed style=%s model=%s", style, model)
                return None
            except Exception as exc:
                last_error = exc
                logger.exception("GPT Image background generation failed style=%s model=%s", style, model)
                return None

        if last_error:
            logger.error("All GPT Image models failed for style=%s: %s", style, last_error)
        return None
    except Exception:
        logger.exception("GPT Image background generation failed style=%s", style)
        return None


def _background_path(user_id: str, style: str, cache_key: str) -> Path:
    bg_dir = _background_dir()
    bg_dir.mkdir(parents=True, exist_ok=True)
    safe_user = user_id.replace("/", "_")
    return bg_dir / f"{safe_user}_{style}_{cache_key}.png"


def load_background(path: str | Path) -> Image.Image | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return Image.open(p).convert("RGB")
    except Exception:
        logger.exception("Failed to load background %s", p)
        return None


def generate_backgrounds_for_variants(
    variants: list[dict],
    *,
    user_id: str,
    recipient: str,
    occasion: str | None,
    visual_hints: list[str],
    iteration: int = 1,
    force_refresh: bool = False,
) -> dict[str, str]:
    """Generate (or load cached) DALL-E backgrounds per style. Returns style → file path."""
    if not is_dalle_enabled():
        return {}

    paths: dict[str, str] = {}
    styles = {v.get("style", "heartfelt") for v in variants}

    def _generate_one(style: str) -> tuple[str, str | None]:
        key = _cache_key(style, occasion, recipient, visual_hints, iteration)
        path = _background_path(user_id, style, key)
        if path.exists() and not force_refresh:
            return style, str(path)

        img = generate_background_image(
            style,
            recipient=recipient,
            occasion=occasion,
            visual_hints=visual_hints,
        )
        if img is None:
            return style, None
        img.save(path, format="PNG")
        return style, str(path)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_generate_one, style): style for style in styles}
        for future in as_completed(futures):
            style, path = future.result()
            if path:
                paths[style] = path

    return paths


def generate_background_for_style(
    style: str,
    *,
    user_id: str,
    recipient: str,
    occasion: str | None,
    visual_hints: list[str],
    design_feedback: list[str],
    iteration: int,
    force_refresh: bool = True,
) -> str | None:
    """Generate one background for the selected design during refinement."""
    if not is_dalle_enabled():
        return None

    key = _cache_key(style, occasion, recipient, visual_hints, iteration, design_feedback)
    path = _background_path(user_id, style, key)
    if path.exists() and not force_refresh:
        return str(path)

    img = generate_background_image(
        style,
        recipient=recipient,
        occasion=occasion,
        visual_hints=visual_hints,
        design_feedback=design_feedback,
    )
    if img is None:
        return None
    img.save(path, format="PNG")
    return str(path)


def backgrounds_as_images(paths: dict[str, str]) -> dict[str, Image.Image]:
    loaded: dict[str, Image.Image] = {}
    for style, path in paths.items():
        img = load_background(path)
        if img is not None:
            loaded[style] = img
    return loaded
