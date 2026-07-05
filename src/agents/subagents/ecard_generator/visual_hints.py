"""Extract visual preferences from user feedback for card rendering."""

COLOR_HINTS = {
    "pink": (255, 182, 193),
    "rose": (255, 182, 193),
    "blue": (173, 216, 230),
    "gold": (255, 215, 140),
    "green": (180, 220, 180),
    "purple": (200, 180, 230),
    "red": (255, 160, 160),
    "pastel": (255, 240, 245),
    "warm": (255, 228, 196),
    "cool": (220, 230, 255),
}

STYLE_KEYWORDS = {
    "minimal": "minimal",
    "simple": "minimal",
    "floral": "floral",
    "flowers": "floral",
    "colorful": "colorful",
    "bright": "colorful",
    "elegant": "elegant",
    "classic": "elegant",
}


def extract_visual_hints(text: str, existing: list[str] | None = None) -> list[str]:
    """Merge new hints from feedback with any already stored."""
    hints = list(existing or [])
    lower = text.lower()
    for word in COLOR_HINTS:
        if word in lower and word not in hints:
            hints.append(word)
    for word, style in STYLE_KEYWORDS.items():
        if word in lower and style not in hints:
            hints.append(style)
    if any(w in lower for w in ("animate", "animated", "gif", "motion")):
        if "animate" not in hints:
            hints.append("animate")
    if any(w in lower for w in ("static", "jpeg", "jpg", "no animation")):
        if "static" not in hints:
            hints.append("static")
    return hints


def wants_animation(visual_hints: list[str], style: str) -> bool:
    if "static" in visual_hints:
        return False
    if "animate" in visual_hints:
        return True
    return style in ("heartfelt", "funny")
