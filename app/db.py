"""SQLite layer: subscribers, news de-duplication, and pending articles queue.

Includes performance pragmas (WAL, synchronous=NORMAL, busy_timeout) and
maintenance helpers (prune, ANALYZE, VACUUM) for production durability.
"""
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

CREATE INDEX IF NOT EXISTS idx_subs_active     ON subscribers(active);
CREATE INDEX IF NOT EXISTS idx_pending_status  ON pending_articles(status);
CREATE INDEX IF NOT EXISTS idx_pending_fetched ON pending_articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_seen_seen_at    ON seen_news(seen_at);
"""


# Pragmas applied to every connection. Documented values:
#   journal_mode=WAL       — Write-Ahead Logging: readers don't block writers.
#                            Persistent setting (survives reopen).
#   synchronous=NORMAL     — Safe with WAL; ~10x faster than FULL.
#   busy_timeout=5000      — Wait up to 5s if DB is locked instead of failing.
#   temp_store=MEMORY      — Sort + temp tables in RAM, not on disk.
#   foreign_keys=ON        — Enforce FK constraints (defensive; we don't use
#                            them yet but future-proofs the schema).
_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA foreign_keys=ON",
)


@dataclass(frozen=True)
class DBStats:
    """Snapshot of database health metrics. Returned by Database.stats()."""
    file_bytes: int            # actual file size on disk
    page_count: int            # total pages allocated
    page_size: int             # bytes per page
    freelist_pages: int        # pages reclaimable by VACUUM
    subs_active: int           # active subscribers (active=1)
    subs_inactive: int         # opted-out / stub rows (active=0)
    seen_news: int             # rows in seen_news
    pending: int               # pending_articles WHERE status='pending'
    approved: int              # status='approved'
    discarded: int             # status='discarded'
    integrity_ok: bool         # PRAGMA integrity_check result

    @property
    def fragmentation_pct(self) -> float:
        if self.page_count == 0:
            return 0.0
        return round(100.0 * self.freelist_pages / self.page_count, 1)

    @property
    def reclaimable_bytes(self) -> int:
        return self.freelist_pages * self.page_size


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
        # Apply performance pragmas to every connection. journal_mode=WAL is
        # persistent; the rest are per-connection but the cost is negligible.
        for pragma in _PRAGMAS:
            try:
                conn.execute(pragma)
            except sqlite3.DatabaseError:
                pass  # don't fail to open the DB if a pragma is unsupported
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

    def prune_old_articles(self, keep_last_days: int = 14) -> int:
        """Delete approved/discarded articles older than `keep_last_days`.
        Returns number of rows deleted."""
        with self._conn() as c:
            cur = c.execute(
                """DELETE FROM pending_articles
                   WHERE status IN ('approved','discarded')
                     AND fetched_at < datetime('now', ?)""",
                (f"-{keep_last_days} days",),
            )
            return cur.rowcount or 0

    # ---------- maintenance ----------
    def prune_inactive_subscribers(self, keep_last_days: int = 90) -> int:
        """Delete subscriber rows that have been inactive (active=0) since
        before `keep_last_days` ago AND were never used to set a language.

        Conservative by design: language=vi (default) + active=0 + old joined_at
        is treated as a stub that's safe to remove. Anything else is kept.
        Returns number of rows deleted.
        """
        with self._conn() as c:
            cur = c.execute(
                """DELETE FROM subscribers
                   WHERE active=0
                     AND language='vi'
                     AND joined_at < datetime('now', ?)""",
                (f"-{keep_last_days} days",),
            )
            return cur.rowcount or 0

    def analyze(self) -> None:
        """Update query planner statistics. Cheap (~ms). Run after large changes."""
        with self._conn() as c:
            c.execute("ANALYZE")

    def vacuum(self) -> None:
        """Rebuild the database file, reclaiming free pages and reducing size.
        Holds a write lock for the duration; can take seconds for large DBs.
        Works in WAL mode (SQLite handles the WAL switch internally).
        """
        with self._conn() as c:
            c.execute("VACUUM")

    def integrity_check(self) -> bool:
        """Return True if PRAGMA integrity_check returns 'ok', else False."""
        with self._conn() as c:
            row = c.execute("PRAGMA integrity_check").fetchone()
            return row is not None and row[0] == "ok"

    def stats(self) -> DBStats:
        """Return a DBStats snapshot for diagnostics."""
        file_bytes = self.path.stat().st_size if self.path.exists() else 0
        with self._conn() as c:
            page_count = c.execute("PRAGMA page_count").fetchone()[0]
            page_size = c.execute("PRAGMA page_size").fetchone()[0]
            freelist = c.execute("PRAGMA freelist_count").fetchone()[0]

            subs_active = c.execute(
                "SELECT COUNT(*) FROM subscribers WHERE active=1"
            ).fetchone()[0]
            subs_inactive = c.execute(
                "SELECT COUNT(*) FROM subscribers WHERE active=0"
            ).fetchone()[0]
            seen = c.execute("SELECT COUNT(*) FROM seen_news").fetchone()[0]
            pending = c.execute(
                "SELECT COUNT(*) FROM pending_articles WHERE status='pending'"
            ).fetchone()[0]
            approved = c.execute(
                "SELECT COUNT(*) FROM pending_articles WHERE status='approved'"
            ).fetchone()[0]
            discarded = c.execute(
                "SELECT COUNT(*) FROM pending_articles WHERE status='discarded'"
            ).fetchone()[0]
            integrity_row = c.execute("PRAGMA integrity_check").fetchone()
            integrity_ok = integrity_row is not None and integrity_row[0] == "ok"

        return DBStats(
            file_bytes=file_bytes,
            page_count=page_count,
            page_size=page_size,
            freelist_pages=freelist,
            subs_active=subs_active,
            subs_inactive=subs_inactive,
            seen_news=seen,
            pending=pending,
            approved=approved,
            discarded=discarded,
            integrity_ok=integrity_ok,
        )

    def optimize(
        self,
        *,
        keep_news_days: int = 30,
        keep_article_days: int = 14,
        keep_inactive_days: int = 90,
        do_vacuum: bool = True,
    ) -> dict:
        """Full maintenance pass: prune old rows, ANALYZE, optionally VACUUM.
        Returns a summary dict with counts of removed rows and size deltas.
        """
        before = self.stats()
        deleted_news = 0
        deleted_articles = 0
        deleted_subs = 0

        with self._conn() as c:
            cur = c.execute(
                "DELETE FROM seen_news WHERE seen_at < datetime('now', ?)",
                (f"-{keep_news_days} days",),
            )
            deleted_news = cur.rowcount or 0

            cur = c.execute(
                """DELETE FROM pending_articles
                   WHERE status IN ('approved','discarded')
                     AND fetched_at < datetime('now', ?)""",
                (f"-{keep_article_days} days",),
            )
            deleted_articles = cur.rowcount or 0

            cur = c.execute(
                """DELETE FROM subscribers
                   WHERE active=0
                     AND language='vi'
                     AND joined_at < datetime('now', ?)""",
                (f"-{keep_inactive_days} days",),
            )
            deleted_subs = cur.rowcount or 0

            c.execute("ANALYZE")

        if do_vacuum:
            self.vacuum()

        after = self.stats()
        return {
            "deleted_news": deleted_news,
            "deleted_articles": deleted_articles,
            "deleted_subscribers": deleted_subs,
            "size_before_bytes": before.file_bytes,
            "size_after_bytes": after.file_bytes,
            "size_freed_bytes": max(before.file_bytes - after.file_bytes, 0),
            "vacuumed": do_vacuum,
        }


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
