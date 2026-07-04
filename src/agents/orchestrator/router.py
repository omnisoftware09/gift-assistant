"""Intent routing — dispatches to sub-agents."""

from src.agents.orchestrator.parser import is_gift_request, parse_gift_request

INTENTS = {
    "gift": ["gift", "present", "recommend", "suggest", "what to get"],
    "event": ["event", "calendar", "schedule", "upcoming"],
    "profile": ["profile", "likes", "interests", "prefers"],
    "ecard": ["ecard", "greeting card", "greeting"],
}

# Event-only phrases; don't treat as gift when no gift trigger present
EVENT_OCCASIONS = ["birthday", "anniversary", "graduation", "wedding"]


def detect_intent(text: str) -> str | None:
    lower = text.lower()

    # Gift takes priority when user asks for recommendations
    if is_gift_request(text) or parse_gift_request(text):
        return "gift"

    for intent, keywords in INTENTS.items():
        if intent == "gift":
            continue
        if any(keyword in lower for keyword in keywords):
            return intent

    # "Sarah's birthday" without gift words → event
    if any(word in lower for word in EVENT_OCCASIONS):
        return "event"

    return None
