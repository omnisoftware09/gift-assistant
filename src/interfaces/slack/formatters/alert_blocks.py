import json

from src.storage.models.calendar_event import CalendarEvent
from src.storage.models.gift_request import GiftRequest


def build_proactive_alert(event: CalendarEvent, gift: GiftRequest) -> dict:
    """Build Slack blocks for a proactive gift alert."""
    payload = json.dumps(
        {
            "event_id": event.id,
            "recipient": gift.recipient,
            "occasion": gift.occasion,
        }
    )

    when = event.when_label()
    occasion = gift.occasion or "event"
    text = (
        f"*{gift.recipient}'s {occasion}* is coming up {when} "
        f"({event.start.strftime('%A, %B %-d')}).\n"
        "Do you want me to search for gift ideas?"
    )

    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Yes, search gifts",
                        },
                        "style": "primary",
                        "action_id": "proactive_gift_search",
                        "value": payload,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Remind me later",
                        },
                        "action_id": "proactive_remind_later",
                        "value": payload,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Skip"},
                        "action_id": "proactive_skip",
                        "value": payload,
                    },
                ],
            },
        ],
    }
