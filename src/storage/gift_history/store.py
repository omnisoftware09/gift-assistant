"""CRUD for recipient profiles and gift history."""

from src.storage.gift_history.db import get_connection, init_db
from src.storage.models.recipient_context import PastGift, RecipientContext


class GiftHistoryStore:
    def __init__(self):
        init_db()

    def get_or_create_recipient(self, name: str) -> int:
        clean = name.strip().title()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM recipients WHERE name = ? COLLATE NOCASE",
                (clean,),
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO recipients (name) VALUES (?)",
                (clean,),
            )
            conn.commit()
            return int(cur.lastrowid)

    def set_age_range(self, name: str, age_range: str) -> None:
        clean = name.strip().title()
        recipient_id = self.get_or_create_recipient(clean)
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE recipients SET age_range = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (age_range.strip(), recipient_id),
            )
            conn.commit()

    def get_recipient_context(self, name: str) -> RecipientContext:
        clean = name.strip().title()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, age_range FROM recipients WHERE name = ? COLLATE NOCASE",
                (clean,),
            ).fetchone()
            if not row:
                return RecipientContext(name=clean)

            gifts = conn.execute(
                """
                SELECT title, category, occasion, selected_at
                FROM gift_history
                WHERE recipient_id = ?
                ORDER BY selected_at DESC
                LIMIT 20
                """,
                (row["id"],),
            ).fetchall()

        past = [
            PastGift(
                title=g["title"],
                category=g["category"] or "general",
                occasion=g["occasion"],
                selected_at=g["selected_at"],
            )
            for g in gifts
        ]
        return RecipientContext(
            name=row["name"],
            age_range=row["age_range"],
            past_gifts=past,
        )

    def save_selected_gift(
        self,
        name: str,
        title: str,
        category: str,
        occasion: str | None = None,
        description: str | None = None,
    ) -> int:
        recipient_id = self.get_or_create_recipient(name)
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO gift_history (recipient_id, title, category, occasion, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    recipient_id,
                    title.strip(),
                    (category or "general").strip().lower(),
                    occasion,
                    description,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)


_store: GiftHistoryStore | None = None


def get_gift_history_store() -> GiftHistoryStore:
    global _store
    if _store is None:
        _store = GiftHistoryStore()
    return _store
