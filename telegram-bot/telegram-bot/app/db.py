"""SQLite layer: subscriber list + news de-duplication."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
    active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS seen_news (
    guid       TEXT PRIMARY KEY,
    seen_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subs_active ON subscribers(active);
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)  # autocommit
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ---------- subscribers ----------
    def add_subscriber(self, user_id: int, username: str | None, first_name: str | None) -> bool:
        """Returns True if newly added, False if already existed (and reactivated)."""
        with self._conn() as c:
            row = c.execute("SELECT active FROM subscribers WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO subscribers(user_id, username, first_name) VALUES(?,?,?)",
                    (user_id, username, first_name),
                )
                return True
            c.execute(
                "UPDATE subscribers SET active=1, username=?, first_name=? WHERE user_id=?",
                (username, first_name, user_id),
            )
            return False

    def remove_subscriber(self, user_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE subscribers SET active=0 WHERE user_id=?", (user_id,))

    def active_subscriber_ids(self) -> list[int]:
        with self._conn() as c:
            rows = c.execute("SELECT user_id FROM subscribers WHERE active=1").fetchall()
            return [r["user_id"] for r in rows]

    def subscriber_count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM subscribers WHERE active=1").fetchone()[0]

    # ---------- news dedup ----------
    def is_news_seen(self, guid: str) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM seen_news WHERE guid=?", (guid,)).fetchone() is not None

    def mark_news_seen(self, guid: str) -> None:
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO seen_news(guid) VALUES(?)", (guid,))

    def prune_old_news(self, keep_last_days: int = 30) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM seen_news WHERE seen_at < datetime('now', ?)",
                (f"-{keep_last_days} days",),
            )
