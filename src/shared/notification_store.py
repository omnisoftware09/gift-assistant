"""Track which proactive alerts have been sent."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("gift_assistant.notification_store")

DEFAULT_STORE = Path("data/notified_events.json")


class NotificationStore:
    def __init__(self, path: Path | str = DEFAULT_STORE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        raw = self.path.read_text().strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid notification store at %s; starting fresh", self.path)
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def should_notify(self, event_id: str) -> bool:
        entry = self._data.get(event_id)
        if not entry:
            return True
        status = entry.get("status")
        if status == "skipped":
            return False
        if status == "snoozed":
            snooze_until = entry.get("snooze_until")
            if snooze_until and datetime.fromisoformat(snooze_until) > datetime.now():
                return False
        if status == "notified":
            return False
        return True

    def mark_notified(self, event_id: str) -> None:
        self._data[event_id] = {
            "status": "notified",
            "notified_at": datetime.now().isoformat(),
        }
        self._save()

    def mark_skipped(self, event_id: str) -> None:
        self._data[event_id] = {
            "status": "skipped",
            "skipped_at": datetime.now().isoformat(),
        }
        self._save()

    def mark_snoozed(self, event_id: str, days: int = 1) -> None:
        until = datetime.now() + timedelta(days=days)
        self._data[event_id] = {
            "status": "snoozed",
            "snooze_until": until.isoformat(),
        }
        self._save()
