"""SQLite layer: subscribers, news de-duplication, and pending articles queue."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
    active     INTEGER NOT NULL DEFAULT 1,
    language   TEXT NOT NULL DEFAULT 'vi'
);

CREATE TABLE IF NOT EXISTS seen_news (
    guid       TEXT PRIMARY KEY,
    seen_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pending_articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guid       TEXT UNIQUE NOT NULL,
    title      TEXT NOT NULL,
    link       TEXT NOT NULL,
    source     TEXT NOT NULL,
    body       TEXT NOT NULL,
    image_url  TEXT,
    published  TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    status     TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','discarded'))
);

CREATE INDEX IF NOT EXISTS idx_subs_active ON subscribers(active);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_articles(status);
"""


@dataclass
class PendingArticle:
    id: int
    guid: str
    title: str
    link: str
    source: str
    body: str
    image_url: str | None
    published: str | None
    fetched_at: str
    status: str


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)
            # Migration: add language column if upgrading from older schema.
            try:
                c.execute("ALTER TABLE subscribers ADD COLUMN language TEXT NOT NULL DEFAULT 'vi'")
            except sqlite3.OperationalError:
                pass  # column already exists

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

    def get_user_language(self, user_id: int) -> str | None:
        """Return the saved language code for a user, or None if not set / unknown user."""
        with self._conn() as c:
            row = c.execute(
                "SELECT language FROM subscribers WHERE user_id=?", (user_id,),
            ).fetchone()
            if row is None:
                return None
            return row["language"]

    def set_user_language(self, user_id: int, lang: str) -> None:
        """Store the user's preferred language. Inserts a stub subscriber row
        (active=0) if the user does not yet exist, so language is remembered
        even before /start."""
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM subscribers WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO subscribers(user_id, active, language) VALUES(?, 0, ?)",
                    (user_id, lang),
                )
            else:
                c.execute(
                    "UPDATE subscribers SET language=? WHERE user_id=?",
                    (lang, user_id),
                )

    def active_subscribers_with_language(self) -> list[tuple[int, str]]:
        """Return [(user_id, language)] pairs for all active subscribers."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT user_id, language FROM subscribers WHERE active=1"
            ).fetchall()
            return [(r["user_id"], r["language"]) for r in rows]

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

    # ---------- pending articles ----------
    def save_pending_article(
        self,
        guid: str,
        title: str,
        link: str,
        source: str,
        body: str,
        image_url: str | None,
        published: str | None,
    ) -> int | None:
        """Insert a new pending article. Returns its row id, or None if guid already exists."""
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO pending_articles
                   (guid, title, link, source, body, image_url, published)
                   VALUES (?,?,?,?,?,?,?)""",
                (guid, title, link, source, body, image_url, published),
            )
            if cur.rowcount == 0:
                return None
            return cur.lastrowid

    def get_pending_article(self, article_id: int) -> PendingArticle | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM pending_articles WHERE id=?", (article_id,),
            ).fetchone()
            return _row_to_article(row) if row else None

    def list_pending_articles(self, limit: int = 30) -> list[PendingArticle]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM pending_articles
                   WHERE status='pending'
                   ORDER BY fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [_row_to_article(r) for r in rows]

    def count_pending_articles(self) -> int:
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM pending_articles WHERE status='pending'"
            ).fetchone()[0]

    def update_article_body(self, article_id: int, new_body: str) -> bool:
        with self._conn() as c:
            cur = c.execute(
                "UPDATE pending_articles SET body=? WHERE id=? AND status='pending'",
                (new_body, article_id),
            )
            return cur.rowcount > 0

    def set_article_status(self, article_id: int, status: str) -> bool:
        if status not in ("pending", "approved", "discarded"):
            raise ValueError(f"invalid status: {status}")
        with self._conn() as c:
            cur = c.execute(
                "UPDATE pending_articles SET status=? WHERE id=?",
                (status, article_id),
            )
            return cur.rowcount > 0

    def prune_old_articles(self, keep_last_days: int = 14) -> None:
        with self._conn() as c:
            c.execute(
                """DELETE FROM pending_articles
                   WHERE status IN ('approved','discarded')
                     AND fetched_at < datetime('now', ?)""",
                (f"-{keep_last_days} days",),
            )


def _row_to_article(row: sqlite3.Row) -> PendingArticle:
    return PendingArticle(
        id=row["id"],
        guid=row["guid"],
        title=row["title"],
        link=row["link"],
        source=row["source"],
        body=row["body"],
        image_url=row["image_url"],
        published=row["published"],
        fetched_at=row["fetched_at"],
        status=row["status"],
    )
