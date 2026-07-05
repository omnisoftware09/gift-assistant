"""SQLite schema for recipient profiles and gift history."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = "data/gift_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    age_range TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gift_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    occasion TEXT,
    description TEXT,
    selected_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (recipient_id) REFERENCES recipients(id)
);

CREATE INDEX IF NOT EXISTS idx_gift_history_recipient ON gift_history(recipient_id);

CREATE TABLE IF NOT EXISTS ecards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    style TEXT NOT NULL DEFAULT 'heartfelt',
    headline TEXT NOT NULL,
    message TEXT NOT NULL,
    sign_off TEXT,
    occasion TEXT,
    selected_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (recipient_id) REFERENCES recipients(id)
);

CREATE INDEX IF NOT EXISTS idx_ecards_recipient ON ecards(recipient_id);
"""


def get_db_path() -> Path:
    path = Path(os.getenv("GIFT_HISTORY_DB", DEFAULT_DB))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
