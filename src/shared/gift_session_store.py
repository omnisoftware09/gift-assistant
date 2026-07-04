"""Active gift recommendation sessions (refinement loop)."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_STORE = Path("data/gift_sessions.json")


@dataclass
class GiftSession:
    user_id: str
    recipient: str
    occasion: str | None = None
    feedback: list[str] = field(default_factory=list)
    last_ranked: list[dict] = field(default_factory=list)
    iteration: int = 1
    age_range: str | None = None

    def feedback_text(self) -> str:
        return "\n".join(f"- {f}" for f in self.feedback) if self.feedback else ""


class GiftSessionStore:
    def __init__(self, path: Path | str = DEFAULT_STORE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def get(self, user_id: str) -> GiftSession | None:
        raw = self._data.get(user_id)
        if not raw:
            return None
        return GiftSession(**raw)

    def start(
        self,
        user_id: str,
        recipient: str,
        occasion: str | None,
        last_ranked: list[dict],
        age_range: str | None = None,
    ) -> GiftSession:
        session = GiftSession(
            user_id=user_id,
            recipient=recipient,
            occasion=occasion,
            last_ranked=last_ranked,
            iteration=1,
            age_range=age_range,
        )
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def update_after_iteration(
        self,
        user_id: str,
        feedback: str,
        last_ranked: list[dict],
    ) -> GiftSession | None:
        session = self.get(user_id)
        if not session:
            return None
        session.feedback.append(feedback)
        session.last_ranked = last_ranked
        session.iteration += 1
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def clear(self, user_id: str) -> None:
        if user_id in self._data:
            del self._data[user_id]
            self._save()


_store: GiftSessionStore | None = None


def get_gift_session_store() -> GiftSessionStore:
    global _store
    if _store is None:
        _store = GiftSessionStore()
    return _store
