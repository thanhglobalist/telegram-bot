"""Shared signal payload parser + formatter.

Both the webhook receiver and the email bridge funnel raw messages through
this module, so signals look identical regardless of source.

Accepted payload formats:

1. JSON (recommended for TradingView webhooks):
   {
     "action": "buy" | "sell" | "long" | "short",
     "symbol": "BTCUSDT",
     "price": 65000,
     "sl":    64000,
     "tp":    67000,
     "tp1":   66800,         # optional secondary targets
     "tp2":   68500,
     "note":  "RSI oversold + EMA cross",
     "source": "TradingView"  # optional override label
   }

2. Plain text (free-form, used when TradingView free plan emails arrive):
   The whole text is forwarded after light cleaning. The parser tries to
   detect symbol/action lines but gracefully falls through to passthrough.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _esc(s: Any) -> str:
    s = str(s)
    for a, b in _HTML_ESCAPES.items():
        s = s.replace(a, b)
    return s


@dataclass
class Signal:
    raw: str
    source: str = "External"
    action: str | None = None      # "BUY" / "SELL"
    symbol: str | None = None
    price: str | None = None
    sl: str | None = None
    tps: list[str] = field(default_factory=list)
    note: str | None = None

    def to_html(self) -> str:
        """Render a Telegram HTML message. Mirrors the /signal layout."""
        head_bits = []
        if self.action:
            head_bits.append(f"<b>{_esc(self.action)}</b>")
        if self.symbol:
            head_bits.append(f"<b>{_esc(self.symbol)}</b>")
        head = " ".join(head_bits) if head_bits else "<b>SIGNAL</b>"

        lines = [
            "📈 <b>TRADING SIGNAL</b>",
            "━━━━━━━━━━━━━━━━━━━",
            head,
        ]
        if self.price:
            lines.append(f"Entry: <code>{_esc(self.price)}</code>")
        if self.sl:
            lines.append(f"SL: <code>{_esc(self.sl)}</code>")
        for i, tp in enumerate(self.tps, 1):
            label = f"TP{i}" if len(self.tps) > 1 else "TP"
            lines.append(f"{label}: <code>{_esc(tp)}</code>")
        if self.note:
            lines.append(f"📝 {_esc(self.note)}")

        # If we have nothing structured at all, fall back to the raw text
        if not any([self.action, self.symbol, self.price, self.sl, self.tps, self.note]):
            lines.append(_esc(self.raw.strip()))

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<i>via {_esc(self.source)} · ⚠️ Not financial advice.</i>")
        return "\n".join(lines)


# ---------- parsers ---------------------------------------------------------


_ACTION_MAP = {
    "buy": "BUY", "long": "BUY", "open_long": "BUY", "enter_long": "BUY",
    "sell": "SELL", "short": "SELL", "open_short": "SELL", "enter_short": "SELL",
}


def _norm_action(a: str | None) -> str | None:
    if not a:
        return None
    return _ACTION_MAP.get(a.strip().lower(), a.strip().upper())


def parse_payload(raw: str, source: str = "External") -> Signal:
    """Parse a raw payload (JSON or text) into a Signal.

    Never raises — falls back to a passthrough Signal so the user always
    sees *something* even if the source sent garbage."""
    raw = (raw or "").strip()
    if not raw:
        return Signal(raw="(empty payload)", source=source)

    # Try JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return _from_json(data, source=source, raw=raw)
    except json.JSONDecodeError:
        pass

    # Fall back to text heuristics
    return _from_text(raw, source=source)


def _from_json(d: dict, *, source: str, raw: str) -> Signal:
    # Collect TP fields: "tp", "tp1", "tp2", "take_profit", "targets": [..]
    tps: list[str] = []
    if "targets" in d and isinstance(d["targets"], list):
        tps = [str(t) for t in d["targets"]]
    else:
        for key in ("tp", "tp1", "tp2", "tp3", "take_profit", "takeProfit"):
            if d.get(key) not in (None, ""):
                tps.append(str(d[key]))

    sig = Signal(
        raw=raw,
        source=str(d.get("source") or source),
        action=_norm_action(d.get("action") or d.get("side") or d.get("strategy.order.action")),
        symbol=str(d["symbol"]).upper() if d.get("symbol") else (
            str(d["ticker"]).upper() if d.get("ticker") else None
        ),
        price=str(d.get("price") or d.get("entry") or d.get("close") or "") or None,
        sl=str(d.get("sl") or d.get("stop_loss") or d.get("stopLoss") or "") or None,
        tps=tps,
        note=(str(d["note"]) if d.get("note") else
              str(d["message"]) if d.get("message") else None),
    )
    return sig


# Loose patterns for free-form text (e.g. plain-text TradingView emails)
_RX_SYMBOL = re.compile(r"\b([A-Z]{2,8}(?:USDT?|USD|EUR|JPY|GBP|BTC|ETH)?)\b")
_RX_ACTION = re.compile(r"\b(BUY|SELL|LONG|SHORT)\b", re.I)
_RX_ENTRY  = re.compile(r"(?:entry|price|@)[^\d\-]*(-?\d[\d.,]*)", re.I)
_RX_SL     = re.compile(r"\b(?:sl|stop[\s-]?loss)\b[^\d\-]*(-?\d[\d.,]*)", re.I)
_RX_TP     = re.compile(r"\b(?:tp\d?|take[\s-]?profit)\b[^\d\-]*(-?\d[\d.,]*)", re.I)


def _from_text(text: str, *, source: str) -> Signal:
    action = None
    if m := _RX_ACTION.search(text):
        action = _norm_action(m.group(1))

    symbol = None
    # Skip the action word so we don't pick "LONG" as a symbol
    cleaned = _RX_ACTION.sub("", text)
    if m := _RX_SYMBOL.search(cleaned):
        symbol = m.group(1).upper()

    price = (m := _RX_ENTRY.search(text)) and m.group(1)
    sl = (m := _RX_SL.search(text)) and m.group(1)
    tps = [m.group(1) for m in _RX_TP.finditer(text)]

    return Signal(
        raw=text,
        source=source,
        action=action,
        symbol=symbol,
        price=price,
        sl=sl,
        tps=tps,
    )
