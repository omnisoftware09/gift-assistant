import json

from slack_bolt import App

from src.agents.subagents.gift_recommender.agent import handle_gift_request
from src.interfaces.slack.formatters.responses import format_response
from src.shared.notification_store import NotificationStore
from src.storage.models.gift_request import GiftRequest


def register_action_handlers(app: App) -> None:
    store = NotificationStore()

    @app.action("proactive_gift_search")
    def on_gift_search(ack, body, client, logger):
        ack()
        payload = _payload_from_action(body)
        try:
            request = GiftRequest(
                recipient=payload["recipient"],
                occasion=payload.get("occasion"),
            )
            response = handle_gift_request(request)
            _post_in_thread(client, body, **format_response(response))
        except Exception:
            logger.exception("proactive_gift_search failed")
            _post_in_thread(client, body, text="Sorry, I couldn't search for gifts.")

    @app.action("proactive_remind_later")
    def on_remind_later(ack, body, client, logger):
        ack()
        payload = _payload_from_action(body)
        try:
            store.mark_snoozed(payload["event_id"], days=1)
            _post_in_thread(
                client,
                body,
                text=(
                    f"Got it — I'll remind you about *{payload['recipient']}'s "
                    f"{payload.get('occasion', 'event')}* again tomorrow."
                ),
            )
        except Exception:
            logger.exception("proactive_remind_later failed")

    @app.action("proactive_skip")
    def on_skip(ack, body, client, logger):
        ack()
        payload = _payload_from_action(body)
        try:
            store.mark_skipped(payload["event_id"])
            _post_in_thread(
                client,
                body,
                text=(
                    f"Skipped — I won't remind you about *{payload['recipient']}'s "
                    f"{payload.get('occasion', 'event')}* again."
                ),
            )
        except Exception:
            logger.exception("proactive_skip failed")


def _payload_from_action(body: dict) -> dict:
    return json.loads(body["actions"][0]["value"])


def _post_in_thread(client, body, **kwargs):
    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=body["message"]["ts"],
        **kwargs,
    )
