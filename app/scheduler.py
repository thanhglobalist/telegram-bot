"""Schedule future signals and broadcasts.

Supports two time formats:
  • Relative delays:  30s, 15m, 2h, 1d  (combine: 1h30m, 2d4h)
  • Absolute times:   17:30        → today at 17:30 (or tomorrow if past)
                      2026-05-06 09:00  → exact datetime

Times are interpreted in the bot's configured timezone (cfg.timezone).
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

# Matches "1h30m", "45s", "2d", etc.
_DURATION_RE = re.compile(
    r"^\s*(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\s*$",
    re.IGNORECASE,
)


@dataclass
class ScheduledJob:
    """Lightweight metadata for a scheduled broadcast."""
    job_id: str
    kind: str              # "signal" or "broadcast"
    body: str              # raw message body (without /command prefix)
    photo_file_id: str | None
    fire_at: datetime      # tz-aware
    created_by: int        # admin user id

    def human_time(self) -> str:
        return self.fire_at.strftime("%Y-%m-%d %H:%M %Z")


class TimerError(ValueError):
    """Raised when a timer string cannot be parsed.

    Carries an i18n message key and optional format variables; the caller
    in bot.py is responsible for translating the message into the user's
    preferred language.
    """

    def __init__(self, key: str, **fmt):
        self.key = key
        self.fmt = fmt
        super().__init__(key)


def parse_when(when: str, tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """Parse a time spec into a tz-aware datetime in `tz`.

    Accepts:
      • Relative:  "30s", "15m", "2h", "1d", "1h30m", "2d4h"
      • Absolute:  "HH:MM"               → today (or tomorrow if past) at HH:MM
                   "YYYY-MM-DD HH:MM"     → exact datetime
                   "YYYY-MM-DD HH:MM:SS"  → exact datetime
    """
    if now is None:
        now = datetime.now(tz)
    when = when.strip()
    if not when:
        raise TimerError("err_empty_time")

    # 1) Relative duration
    m = _DURATION_RE.match(when)
    if m and any(m.groups()):
        days = int(m.group(1) or 0)
        hours = int(m.group(2) or 0)
        minutes = int(m.group(3) or 0)
        seconds = int(m.group(4) or 0)
        delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        if delta.total_seconds() <= 0:
            raise TimerError("err_duration_zero")
        if delta.total_seconds() > 30 * 24 * 3600:
            raise TimerError("err_duration_too_long")
        return now + delta

    # 2) Absolute HH:MM (today, rolls to tomorrow if already past)
    if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", when):
        parts = when.split(":")
        hh, mm = int(parts[0]), int(parts[1])
        ss = int(parts[2]) if len(parts) > 2 else 0
        target = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    # 3) Absolute YYYY-MM-DD HH:MM[:SS]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            naive = datetime.strptime(when, fmt)
        except ValueError:
            continue
        target = naive.replace(tzinfo=tz)
        if target <= now:
            raise TimerError(
                "err_in_past",
                when=target.strftime("%Y-%m-%d %H:%M"),
            )
        return target

    raise TimerError("err_unknown_time")


def split_when_and_body(raw: str) -> tuple[str, str]:
    """Split a /schedule argument string into (when, body).

    The first whitespace-delimited token is the duration (e.g. `30m`).
    Quoted absolute datetimes are also supported:
        '2026-05-06 09:00' BTCUSDT LONG ...

    If the user typed an absolute date *without* quotes
    (`2026-05-06 09:00 BTC...`), we detect the YYYY-MM-DD HH:MM pattern.
    """
    raw = raw.strip()
    if not raw:
        return "", ""

    # Quoted form: "..." body
    if raw.startswith(('"', "'")):
        quote = raw[0]
        end = raw.find(quote, 1)
        if end > 1:
            return raw[1:end].strip(), raw[end + 1:].strip()

    # YYYY-MM-DD HH:MM form (with or without seconds)
    m = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?)\s+(.*)$", raw)
    if m:
        return m.group(1), m.group(2).strip()

    # Default: first token is the duration
    parts = raw.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()
