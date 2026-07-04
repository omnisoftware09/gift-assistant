"""Parse user replies during the gift refinement loop."""

import re

DONE_PATTERN = re.compile(r"^(?:done|cancel|exit|stop|quit|finish)$", re.IGNORECASE)
SELECT_PATTERN = re.compile(
    r"^(?:(?:select|pick|choose|option|#)\s*)?([1-3])\s*\.?$",
    re.IGNORECASE,
)


def parse_gift_session_reply(text: str) -> tuple[str, int | None]:
    """
    Returns (action, index) where action is:
      'done' | 'select' | 'feedback'
    index is 0-based for select (0, 1, 2).
    """
    message = text.strip()
    if not message:
        return "feedback", None

    if DONE_PATTERN.match(message):
        return "done", None

    match = SELECT_PATTERN.match(message)
    if match:
        return "select", int(match.group(1)) - 1

    return "feedback", None
