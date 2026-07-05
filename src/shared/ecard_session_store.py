"""Active eCard refinement sessions."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_STORE = Path("data/ecard_sessions.json")


@dataclass
class EcardSession:
    user_id: str
    recipient: str
    occasion: str | None = None
    feedback: list[str] = field(default_factory=list)
    visual_hints: list[str] = field(default_factory=list)
    backgrounds: dict[str, str] = field(default_factory=dict)
    last_variants: list[dict] = field(default_factory=list)
    iteration: int = 1


class EcardSessionStore:
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

    def get(self, user_id: str) -> EcardSession | None:
        raw = self._data.get(user_id)
        if not raw:
            return None
        raw.setdefault("visual_hints", [])
        raw.setdefault("backgrounds", {})
        return EcardSession(**raw)

    def start(
        self,
        user_id: str,
        recipient: str,
        occasion: str | None,
        last_variants: list[dict],
        visual_hints: list[str] | None = None,
        backgrounds: dict[str, str] | None = None,
    ) -> EcardSession:
        session = EcardSession(
            user_id=user_id,
            recipient=recipient,
            occasion=occasion,
            last_variants=last_variants,
            iteration=1,
            visual_hints=list(visual_hints or []),
            backgrounds=dict(backgrounds or {}),
        )
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def update_after_iteration(
        self,
        user_id: str,
        feedback: str,
        last_variants: list[dict],
        visual_hints: list[str] | None = None,
        backgrounds: dict[str, str] | None = None,
    ) -> EcardSession | None:
        session = self.get(user_id)
        if not session:
            return None
        session.feedback.append(feedback)
        session.last_variants = last_variants
        session.iteration += 1
        if visual_hints is not None:
            session.visual_hints = visual_hints
        if backgrounds is not None:
            session.backgrounds = backgrounds
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def clear(self, user_id: str) -> None:
        if user_id in self._data:
            del self._data[user_id]
            self._save()


_store: EcardSessionStore | None = None


def get_ecard_session_store() -> EcardSessionStore:
    global _store
    if _store is None:
        _store = EcardSessionStore()
    return _store
