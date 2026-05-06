"""IMAP email bridge.

Lets free-plan TradingView users receive automated signals: TradingView
sends an email when an alert fires, this bridge picks it up within seconds
and forwards it through the same broadcast path.

Connects to an IMAP mailbox (e.g. Gmail with an App Password), watches
INBOX for new messages from a configured sender, parses the body, and
calls `on_signal(html)`.

Strategy
--------
Polling every N seconds is simpler and more reliable across providers
than IDLE. Default 20s — tunable via .env. Once a message is processed
it's marked \\Seen so it won't be re-processed.
"""
from __future__ import annotations

import asyncio
import email
import logging
import re
from email.header import decode_header
from email.message import Message
from typing import Awaitable, Callable

from imap_tools import MailBox, AND

from .signals import parse_payload

log = logging.getLogger(__name__)


def _decode(s: str | bytes | None) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8", errors="replace")
        except Exception:
            return s.decode("latin-1", errors="replace")
    parts = decode_header(s)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


_RX_HTML_TAGS = re.compile(r"<[^>]+>")
_RX_WS = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    return _RX_WS.sub(" ", _RX_HTML_TAGS.sub(" ", s)).strip()


class EmailBridge:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender_filter: str | None,
        poll_seconds: int,
        on_signal: Callable[[str], Awaitable[None]],
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender_filter = (sender_filter or "").strip().lower() or None
        self.poll_seconds = max(5, poll_seconds)
        self.on_signal = on_signal
        self._stop = asyncio.Event()

    async def run(self) -> None:
        log.info(
            "Email bridge starting: host=%s user=%s filter=%s poll=%ds",
            self.host, self.username, self.sender_filter or "(any)", self.poll_seconds,
        )
        while not self._stop.is_set():
            try:
                # imap_tools is sync, run in a worker thread
                processed = await asyncio.to_thread(self._poll_once)
                if processed:
                    log.info("Email bridge: forwarded %d message(s)", processed)
            except Exception:
                log.exception("Email bridge poll failed; retrying after backoff")
                await asyncio.sleep(self.poll_seconds * 2)
                continue
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()

    # ---- internals (sync; called from a thread) ----
    def _poll_once(self) -> int:
        count = 0
        with MailBox(self.host, self.port).login(self.username, self.password) as mb:
            mb.folder.set("INBOX")
            for msg in mb.fetch(AND(seen=False), mark_seen=False, bulk=True):
                if self.sender_filter:
                    sender = (msg.from_ or "").lower()
                    if self.sender_filter not in sender:
                        # Not a TradingView email — leave it alone
                        continue

                body = msg.text or _strip_html(msg.html or "")
                subject = msg.subject or ""
                payload = (body or subject).strip()
                if not payload:
                    continue

                signal = parse_payload(payload, source="TradingView (email)")
                html = signal.to_html()
                # Schedule into the bot's event loop
                fut = asyncio.run_coroutine_threadsafe(
                    self.on_signal(html), _get_loop()
                )
                # Wait briefly so we don't mark-seen before the broadcast is queued
                try:
                    fut.result(timeout=10)
                except Exception:
                    log.exception("Forwarding email signal failed")
                    continue

                mb.flag(msg.uid, ["\\Seen"], True)
                count += 1
        return count


# Helper to grab the running loop from the worker thread
_main_loop: asyncio.AbstractEventLoop | None = None


def install_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def _get_loop() -> asyncio.AbstractEventLoop:
    if _main_loop is None:
        raise RuntimeError("EmailBridge: event loop not installed")
    return _main_loop
