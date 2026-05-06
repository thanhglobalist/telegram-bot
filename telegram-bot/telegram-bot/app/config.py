"""Configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_user_id: int
    channel_id: str  # may be "" if no channel
    daily_news_time: str  # "HH:MM" in Asia/Ho_Chi_Minh
    news_sources: tuple[str, ...]
    news_max_items: int
    db_path: Path
    timezone: str = "Asia/Ho_Chi_Minh"

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

    @classmethod
    def from_env(cls) -> "Config":
        sources_raw = os.getenv("NEWS_SOURCES", "").strip()
        sources = tuple(s.strip() for s in sources_raw.split(",") if s.strip())

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

        return cls(
            bot_token=_required("BOT_TOKEN"),
            admin_user_id=int(_required("ADMIN_USER_ID")),
            channel_id=os.getenv("CHANNEL_ID", "").strip(),
            daily_news_time=os.getenv("DAILY_NEWS_TIME", "07:30").strip(),
            news_sources=sources,
            news_max_items=int(os.getenv("NEWS_MAX_ITEMS", "8")),
            db_path=Path(os.getenv("DB_PATH", "/data/bot.db")),
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
