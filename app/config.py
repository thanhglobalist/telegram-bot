"""Configuration loaded from environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


# Vietnamese-language financial RSS feeds — the only supported defaults
# for IS6FX Vietnam. Hardcoded so the bot can never silently downgrade
# to English sources from a stale .env. (Since v3.3.0 these are *always*
# active; .env can only ADD extra feeds, not replace them.)
DEFAULT_VN_SOURCES: tuple[str, ...] = (
    "https://cafef.vn/thi-truong-chung-khoan.rss",
    "https://vnexpress.net/rss/kinh-doanh.rss",
    "https://vietstock.vn/145/tai-chinh.rss",
)

# Domains we recognize as Vietnamese-language. Used for the startup
# language-mismatch warning. Extend freely.
_VN_DOMAINS: tuple[str, ...] = (
    "cafef.vn",
    "vnexpress.net",
    "vietstock.vn",
    "ndh.vn",
    "tinnhanhchungkhoan.vn",
    "thanhnien.vn",
    "tuoitre.vn",
    "baodautu.vn",
    "vneconomy.vn",
)


def _required(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _parse_admin_ids() -> tuple[int, ...]:
    """
    Parse admin Telegram user IDs.

    Priority:
      1. ADMIN_USER_IDS (comma-separated list, v3.3.0+)
      2. ADMIN_USER_ID  (single ID, legacy — still supported)

    At least one valid ID is required. Duplicates are removed; order preserved.
    """
    raw_list = os.getenv("ADMIN_USER_IDS", "").strip()
    raw_single = os.getenv("ADMIN_USER_ID", "").strip()

    candidates: list[str] = []
    if raw_list:
        candidates.extend(s.strip() for s in raw_list.split(",") if s.strip())
    if raw_single:
        candidates.append(raw_single)

    seen: set[int] = set()
    ids: list[int] = []
    for c in candidates:
        try:
            uid = int(c)
        except ValueError:
            raise RuntimeError(f"Invalid admin user ID: {c!r} (must be a Telegram numeric ID)")
        if uid not in seen:
            seen.add(uid)
            ids.append(uid)

    if not ids:
        raise RuntimeError(
            "Missing admin configuration. Set ADMIN_USER_IDS=<id1>,<id2>,... "
            "(or legacy ADMIN_USER_ID=<id>) in .env"
        )
    return tuple(ids)


def _build_news_sources() -> tuple[str, ...]:
    """
    Build the active news source list.

    Behaviour (v3.3.0+):
      - DEFAULT_VN_SOURCES are ALWAYS included. They cannot be disabled via .env.
      - NEWS_SOURCES env var is *additive*: any feeds listed there are
        appended (after dedup) to the VN defaults.
      - This guarantees a stale or accidentally-overwritten .env on a VPS
        can never strand the bot on the wrong-language feeds.
    """
    extra_raw = os.getenv("NEWS_SOURCES", "").strip()
    extra = tuple(s.strip() for s in extra_raw.split(",") if s.strip())

    sources: list[str] = list(DEFAULT_VN_SOURCES)
    for url in extra:
        if url not in sources:
            sources.append(url)
    return tuple(sources)


def is_vn_feed(url: str) -> bool:
    """Heuristic: does this RSS URL look Vietnamese?"""
    u = url.lower()
    return any(d in u for d in _VN_DOMAINS)


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_user_ids: tuple[int, ...]
    channel_id: str  # may be "" if no channel
    news_sources: tuple[str, ...]
    news_max_items: int
    db_path: Path
    timezone: str = "Asia/Ho_Chi_Minh"
    lang_default: str = "vi"

    # Webhook receiver
    webhook_enabled: bool = False
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_secret: str = ""

    # Email bridge
    email_bridge_enabled: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_sender_filter: str = "noreply@tradingview.com"
    imap_poll_seconds: int = 20

    @property
    def admin_user_id(self) -> int:
        """Primary admin (first in list). Kept for backwards compatibility
        with code that DMs 'the' admin (e.g. weekly maintenance reports)."""
        return self.admin_user_ids[0]

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_user_ids

    @classmethod
    def from_env(cls) -> "Config":
        admin_ids = _parse_admin_ids()
        sources = _build_news_sources()

        webhook_enabled = _bool("WEBHOOK_ENABLED", False)
        webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()
        if webhook_enabled and not webhook_secret:
            raise RuntimeError(
                "WEBHOOK_ENABLED=true but WEBHOOK_SECRET is empty. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        email_enabled = _bool("EMAIL_BRIDGE_ENABLED", False)
        if email_enabled:
            for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"):
                if not os.getenv(k, "").strip():
                    raise RuntimeError(f"EMAIL_BRIDGE_ENABLED=true but {k} is empty")

        lang_default = os.getenv("LANG_DEFAULT", "vi").strip().lower() or "vi"

        cfg = cls(
            bot_token=_required("BOT_TOKEN"),
            admin_user_ids=admin_ids,
            channel_id=os.getenv("CHANNEL_ID", "").strip(),
            news_sources=sources,
            news_max_items=int(os.getenv("NEWS_MAX_ITEMS", "8")),
            db_path=Path(os.getenv("DB_PATH", "/data/bot.db")),
            lang_default=lang_default,
            webhook_enabled=webhook_enabled,
            webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0").strip(),
            webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
            webhook_secret=webhook_secret,
            email_bridge_enabled=email_enabled,
            imap_host=os.getenv("IMAP_HOST", "").strip(),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            imap_user=os.getenv("IMAP_USER", "").strip(),
            imap_password=os.getenv("IMAP_PASSWORD", ""),
            imap_sender_filter=os.getenv("IMAP_SENDER_FILTER", "noreply@tradingview.com").strip(),
            imap_poll_seconds=int(os.getenv("IMAP_POLL_SECONDS", "20")),
        )

        # Startup language-mismatch warning. Logged loudly so a misconfigured
        # VPS surfaces in journalctl/docker logs immediately on boot.
        if lang_default == "vi":
            non_vn = [u for u in cfg.news_sources if not is_vn_feed(u)]
            if non_vn:
                log.warning(
                    "[config] LANG_DEFAULT=vi but %d non-Vietnamese feed(s) detected: %s. "
                    "These were added via NEWS_SOURCES in .env. Default VN feeds are still active.",
                    len(non_vn),
                    ", ".join(non_vn),
                )

        log.info(
            "[config] %d admin(s): %s | %d news feed(s) active | lang=%s",
            len(admin_ids),
            ",".join(str(a) for a in admin_ids),
            len(sources),
            lang_default,
        )

        return cfg
