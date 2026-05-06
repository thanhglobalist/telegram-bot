"""HTTP webhook receiver for TradingView (or any external alert system).

Runs in the same process as the Telegram bot via uvicorn started in a
background asyncio task. No reverse proxy needed for HTTPS termination if
you put Caddy/nginx in front of port 8080.

Endpoints
---------
POST /tv-webhook/{secret}
    Receives an alert payload (JSON or text) and broadcasts it.
    `{secret}` must match WEBHOOK_SECRET. This is the *only* auth.

GET /healthz
    Returns 200 OK for liveness checks.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from .signals import parse_payload

log = logging.getLogger(__name__)


def build_app(*, secret: str, on_signal) -> FastAPI:
    """Create the FastAPI app.

    `on_signal` is an async callable: `await on_signal(signal_html: str)`.
    bot.py supplies it; it ultimately calls the existing _broadcast() helper.
    """
    api = FastAPI(title="Telegram Bot Webhook", docs_url=None, redoc_url=None)

    @api.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @api.post("/tv-webhook/{token}")
    async def webhook(token: str, request: Request) -> dict[str, Any]:
        if not secret or token != secret:
            # 404 (not 401) so casual probes don't learn the path exists
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Accept both JSON and raw text; TradingView sends text by default.
        body = (await request.body()).decode("utf-8", errors="replace").strip()
        if not body:
            raise HTTPException(status_code=400, detail="empty body")

        signal = parse_payload(body, source="TradingView")
        log.info("Webhook signal: %s %s", signal.action or "?", signal.symbol or "?")

        # Don't block the HTTP response on Telegram delivery
        asyncio.create_task(on_signal(signal.to_html()))
        return {"ok": True, "symbol": signal.symbol, "action": signal.action}

    return api


async def serve(api: FastAPI, *, host: str, port: int) -> None:
    """Run uvicorn inside the existing asyncio loop."""
    config = uvicorn.Config(
        api,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    log.info("Webhook server listening on http://%s:%d", host, port)
    await server.serve()
