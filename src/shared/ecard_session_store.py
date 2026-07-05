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
    phase: str = "pick"  # pick | refine
    selected_index: int | None = None
    selected_card: dict | None = None
    design_feedback: list[str] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    visual_hints: list[str] = field(default_factory=list)
    backgrounds: dict[str, str] = field(default_factory=dict)
    selected_background: str | None = None
    last_variants: list[dict] = field(default_factory=list)
    iteration: int = 1
    refine_round: int = 0


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

    def _hydrate(self, raw: dict) -> EcardSession:
        raw.setdefault("visual_hints", [])
        raw.setdefault("backgrounds", {})
        raw.setdefault("design_feedback", [])
        raw.setdefault("phase", "pick")
        raw.setdefault("refine_round", 0)
        return EcardSession(**raw)

    def get(self, user_id: str) -> EcardSession | None:
        raw = self._data.get(user_id)
        if not raw:
            return None
        return self._hydrate(raw)

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
            phase="pick",
            last_variants=last_variants,
            iteration=1,
            visual_hints=list(visual_hints or []),
            backgrounds=dict(backgrounds or {}),
        )
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def select_design(
        self,
        user_id: str,
        index: int,
        card: dict,
        *,
        initial_feedback: str | None = None,
        background_path: str | None = None,
    ) -> EcardSession | None:
        session = self.get(user_id)
        if not session:
            return None
        session.phase = "refine"
        session.selected_index = index
        session.selected_card = dict(card)
        session.refine_round = 0
        session.selected_background = background_path
        if initial_feedback:
            session.design_feedback.append(initial_feedback)
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def update_after_refinement(
        self,
        user_id: str,
        feedback: str,
        card: dict,
        *,
        background_path: str | None = None,
        visual_hints: list[str] | None = None,
    ) -> EcardSession | None:
        session = self.get(user_id)
        if not session:
            return None
        session.design_feedback.append(feedback)
        session.selected_card = dict(card)
        session.refine_round += 1
        if background_path:
            session.selected_background = background_path
        if visual_hints is not None:
            session.visual_hints = visual_hints
        self._data[user_id] = asdict(session)
        self._save()
        return session

    def return_to_pick(self, user_id: str) -> EcardSession | None:
        session = self.get(user_id)
        if not session:
            return None
        session.phase = "pick"
        session.selected_index = None
        session.selected_card = None
        session.selected_background = None
        session.design_feedback = []
        session.refine_round = 0
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
