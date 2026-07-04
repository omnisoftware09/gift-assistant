"""Recipient profile + gift history for recommendations."""

from dataclasses import dataclass, field


@dataclass
class PastGift:
    title: str
    category: str
    occasion: str | None = None
    selected_at: str | None = None


@dataclass
class RecipientContext:
    name: str
    age_range: str | None = None
    past_gifts: list[PastGift] = field(default_factory=list)

    def excluded_categories(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for gift in self.past_gifts:
            cat = (gift.category or "").strip().lower()
            if cat and cat not in seen:
                seen.add(cat)
                out.append(cat)
        return out

    def past_gifts_summary(self) -> str:
        if not self.past_gifts:
            return "No past gifts recorded."
        lines = []
        for g in self.past_gifts:
            occ = f" ({g.occasion})" if g.occasion else ""
            lines.append(f"- {g.title} [{g.category}]{occ}")
        return "\n".join(lines)
