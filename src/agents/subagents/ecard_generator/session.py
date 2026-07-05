"""Parse user replies during the eCard pick / refine phases."""

import re

DONE_PATTERN = re.compile(r"^(?:done|cancel|exit|stop|quit)$", re.IGNORECASE)
FINALIZE_PATTERN = re.compile(
    r"^(?:finalize|save|send|approve|looks good|perfect|ready)$",
    re.IGNORECASE,
)
PICK_SELECT_PATTERN = re.compile(
    r"^(?:(?:select|pick|choose|option|#|design)\s*)?([1-3])\s*\.?$",
    re.IGNORECASE,
)
COMBINED_SELECT_PATTERN = re.compile(
    r"(?:^|\b)(?:design|option|#)\s*([1-3])\s*[:\-,]\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
SWITCH_DESIGN_PATTERN = re.compile(
    r"^(?:pick|switch|change)\s+(?:to\s+)?(?:design\s+)?([1-3])\s*\.?$",
    re.IGNORECASE,
)


def parse_pick_phase_reply(text: str) -> tuple[str, int | None, str | None]:
    """
    Returns (action, index, trailing_feedback).
    action: 'done' | 'select' | 'invalid'
    index: 0-based design index for select
    trailing_feedback: extra instructions when user says e.g. "design 2, add flowers"
    """
    message = text.strip()
    if not message:
        return "invalid", None, None

    if DONE_PATTERN.match(message):
        return "done", None, None

    combined = COMBINED_SELECT_PATTERN.search(message)
    if combined:
        return "select", int(combined.group(1)) - 1, combined.group(2).strip()

    match = PICK_SELECT_PATTERN.match(message)
    if match:
        return "select", int(match.group(1)) - 1, None

    return "invalid", None, None


def parse_refine_phase_reply(text: str) -> tuple[str, int | None, str | None]:
    """
    Returns (action, index, feedback).
    action: 'done' | 'finalize' | 'switch' | 'feedback'
    """
    message = text.strip()
    if not message:
        return "feedback", None, message

    if DONE_PATTERN.match(message):
        return "done", None, None

    if FINALIZE_PATTERN.match(message):
        return "finalize", None, None

    switch = SWITCH_DESIGN_PATTERN.match(message)
    if switch:
        return "switch", int(switch.group(1)) - 1, None

    return "feedback", None, message
