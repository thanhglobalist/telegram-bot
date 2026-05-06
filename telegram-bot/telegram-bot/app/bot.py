"""Main Telegram bot entry point."""
from __future__ import annotations

import asyncio
import logging
from datetime import time as dtime
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from .config import Config
from .db import Database
from .news import fetch_news, NewsItem
from . import webhook as webhook_mod
from . import email_bridge as email_mod

log = logging.getLogger(__name__)

# --- Static text -------------------------------------------------------------

WELCOME = (
    "👋 <b>Welcome.</b>\n\n"
    "You are now subscribed to:\n"
    "  • 📈 Trading signals\n"
    "  • 📰 Daily news digest\n\n"
    "Use /stop to unsubscribe at any time.\n"
    "Use /help for the full command list."
)

HELP_USER = (
    "<b>Commands</b>\n"
    "/start — subscribe to signals + news\n"
    "/stop — unsubscribe\n"
    "/news — get the latest news on demand\n"
    "/help — show this message"
)

HELP_ADMIN = HELP_USER + (
    "\n\n<b>Admin</b>\n"
    "/signal &lt;text&gt; — broadcast a signal\n"
    "/broadcast &lt;text&gt; — send any message to all subscribers + channel\n"
    "/stats — subscriber count\n"
    "/sendnews — trigger the daily digest now"
)


# --- Helpers -----------------------------------------------------------------


def _is_admin(cfg: Config, user_id: int) -> bool:
    return user_id == cfg.admin_user_id


async def _broadcast(
    context: ContextTypes.DEFAULT_TYPE,
    cfg: Config,
    db: Database,
    text: str,
    *,
    parse_mode: str = ParseMode.HTML,
    disable_web_page_preview: bool = False,
) -> tuple[int, int]:
    """Send `text` to channel (if configured) + every active subscriber.
    Returns (delivered, failed). Removes users who blocked the bot."""
    delivered = 0
    failed = 0

    # Channel first
    if cfg.channel_id:
        try:
            await context.bot.send_message(
                chat_id=cfg.channel_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            delivered += 1
        except TelegramError as e:
            log.warning("Channel send failed (%s): %s", cfg.channel_id, e)
            failed += 1

    # Direct subscribers — respect Telegram's 30 msg/sec global limit
    user_ids = db.active_subscriber_ids()
    for i, uid in enumerate(user_ids):
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            delivered += 1
        except Forbidden:
            # User blocked the bot — deactivate them
            db.remove_subscriber(uid)
            failed += 1
        except BadRequest as e:
            log.warning("BadRequest sending to %s: %s", uid, e)
            failed += 1
        except TelegramError as e:
            log.warning("TelegramError sending to %s: %s", uid, e)
            failed += 1

        # Throttle: ~25 msg/sec to stay safely under the 30/sec limit
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1.0)

    return delivered, failed


# --- Command handlers --------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    is_new = db.add_subscriber(user.id, user.username, user.first_name)
    msg = WELCOME if is_new else "✅ You are subscribed (welcome back)."
    await update.effective_message.reply_html(msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    db.remove_subscriber(user.id)
    await update.effective_message.reply_text("👋 Unsubscribed. Send /start to resubscribe.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    text = HELP_ADMIN if user and _is_admin(cfg, user.id) else HELP_USER
    await update.effective_message.reply_html(text)


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text("⛔ This command is for the admin only.")
        return

    if not context.args:
        await update.effective_message.reply_html(
            "Usage:\n<code>/signal BTCUSDT LONG entry=65000 sl=64000 tp=67000</code>\n\n"
            "Everything after /signal is sent verbatim (HTML formatting allowed)."
        )
        return

    body = update.effective_message.text.split(" ", 1)[1].strip()
    text = (
        "📈 <b>TRADING SIGNAL</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"{body}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "<i>⚠️ Not financial advice. Trade at your own risk.</i>"
    )
    delivered, failed = await _broadcast(context, cfg, db, text)
    await update.effective_message.reply_text(
        f"✅ Signal sent. Delivered: {delivered}, failed: {failed}"
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /broadcast <message>")
        return
    body = update.effective_message.text.split(" ", 1)[1].strip()
    delivered, failed = await _broadcast(context, cfg, db, body)
    await update.effective_message.reply_text(
        f"✅ Broadcast sent. Delivered: {delivered}, failed: {failed}"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text(
        f"👥 Active subscribers: {db.subscriber_count()}\n"
        f"📡 Channel: {cfg.channel_id or '(none)'}\n"
        f"🕒 Daily news at: {cfg.daily_news_time} {cfg.timezone}\n"
        f"🔗 Webhook: {'on' if cfg.webhook_enabled else 'off'}"
        + (f" (port {cfg.webhook_port})" if cfg.webhook_enabled else "") + "\n"
        f"📨 Email bridge: {'on' if cfg.email_bridge_enabled else 'off'}"
        + (f" ({cfg.imap_user})" if cfg.email_bridge_enabled else "")
    )


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand news (any user)."""
    cfg: Config = context.application.bot_data["cfg"]
    await update.effective_message.reply_text("Fetching latest news…")
    items = await asyncio.to_thread(fetch_news, cfg.news_sources, 10)
    if not items:
        await update.effective_message.reply_text("No news right now. Try again later.")
        return
    text = _format_digest(items[: cfg.news_max_items])
    await update.effective_message.reply_html(text, disable_web_page_preview=True)


async def cmd_sendnews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text("Triggering daily digest now…")
    await _job_daily_news(context)


# --- Scheduled job -----------------------------------------------------------


def _format_digest(items: list[NewsItem]) -> str:
    lines = ["📰 <b>Daily News Digest</b>", ""]
    lines.extend(item.render() for item in items)
    lines.append("")
    lines.append("<i>Sources fetched from configured RSS feeds / sites.</i>")
    return "\n".join(lines)


async def _job_daily_news(context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]

    items = await asyncio.to_thread(fetch_news, cfg.news_sources, 15)

    # Filter out anything we already sent
    fresh = [i for i in items if not db.is_news_seen(i.guid)]
    if not fresh:
        log.info("Daily news job: nothing new to send")
        return

    digest_items = fresh[: cfg.news_max_items]
    text = _format_digest(digest_items)
    delivered, failed = await _broadcast(
        context, cfg, db, text, disable_web_page_preview=True
    )
    log.info("Daily news sent. Delivered=%d failed=%d", delivered, failed)

    for it in digest_items:
        db.mark_news_seen(it.guid)
    db.prune_old_news(30)


# --- Setup -------------------------------------------------------------------


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Subscribe to signals + news"),
        BotCommand("stop", "Unsubscribe"),
        BotCommand("news", "Get latest news now"),
        BotCommand("help", "Show help"),
    ])
    log.info("Bot commands registered.")

    cfg: Config = application.bot_data["cfg"]
    db: Database = application.bot_data["db"]

    # External signal handler shared by webhook + email bridge
    async def on_external_signal(html: str) -> None:
        """Broadcast a pre-formatted HTML signal to channel + subscribers."""
        # Build a synthetic ContextTypes.DEFAULT_TYPE-like wrapper using the application's bot.
        class _Ctx:
            bot = application.bot
        delivered, failed = await _broadcast(_Ctx(), cfg, db, html)
        log.info("External signal broadcast: delivered=%d failed=%d", delivered, failed)

    # Start webhook server as a background task
    if cfg.webhook_enabled:
        api = webhook_mod.build_app(secret=cfg.webhook_secret, on_signal=on_external_signal)
        application.bot_data["webhook_task"] = asyncio.create_task(
            webhook_mod.serve(api, host=cfg.webhook_host, port=cfg.webhook_port),
            name="webhook-server",
        )

    # Start email bridge as a background task
    if cfg.email_bridge_enabled:
        email_mod.install_loop(asyncio.get_running_loop())
        bridge = email_mod.EmailBridge(
            host=cfg.imap_host,
            port=cfg.imap_port,
            username=cfg.imap_user,
            password=cfg.imap_password,
            sender_filter=cfg.imap_sender_filter,
            poll_seconds=cfg.imap_poll_seconds,
            on_signal=on_external_signal,
        )
        application.bot_data["email_bridge"] = bridge
        application.bot_data["email_task"] = asyncio.create_task(
            bridge.run(), name="email-bridge",
        )


def build_application(cfg: Config) -> Application:
    db = Database(cfg.db_path)

    app = Application.builder().token(cfg.bot_token).post_init(_post_init).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["db"] = db

    # Public
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("news", cmd_news))
    # Admin
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("sendnews", cmd_sendnews))

    # Schedule daily news
    hh, mm = (int(x) for x in cfg.daily_news_time.split(":"))
    tz = ZoneInfo(cfg.timezone)
    app.job_queue.run_daily(
        _job_daily_news,
        time=dtime(hour=hh, minute=mm, tzinfo=tz),
        name="daily_news",
    )
    log.info("Scheduled daily news at %02d:%02d %s", hh, mm, cfg.timezone)

    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    cfg = Config.from_env()
    app = build_application(cfg)
    log.info("Bot starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
