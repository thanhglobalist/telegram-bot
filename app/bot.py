"""Main Telegram bot entry point. Multi-language UI (EN / VI / JA)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from zoneinfo import ZoneInfo

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import i18n
from .config import Config
from .db import Database
from .news import fetch_news, fetch_full_article, NewsItem, FullArticle
from .scheduler import (
    ScheduledJob,
    TimerError,
    parse_when,
    split_when_and_body,
)
from . import webhook as webhook_mod
from . import email_bridge as email_mod

log = logging.getLogger(__name__)

# Telegram caption limit is 1024 chars. If caller text is longer, we send the
# photo with a short caption + a follow-up text message.
CAPTION_MAX = 1024

# --- Visual style guide ------------------------------------------------------
#   ━━━   bold horizontal rule  = card top/bottom
#   ───   thin horizontal rule  = soft section split
#   ├ └   tree connectors       = grouped list items
#   🟢/🔴/🔵 status pills          = at-a-glance state

DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
THIN_DIVIDER = "────────────────────"
BRAND = "IS6FX Vietnam"


# --- Language resolver -------------------------------------------------------


def _resolve_lang(db: Database, user: User | None) -> str:
    """Return the language code to use for `user`.

    Order: stored DB preference → Telegram client language_code → DEFAULT_LANG.
    """
    if user is None:
        return i18n.DEFAULT_LANG
    saved = db.get_user_language(user.id)
    if saved and saved in i18n.LANGUAGES:
        return saved
    return i18n.normalize(getattr(user, "language_code", None))


# Convenience wrapper
def T(key: str, lang: str, **kwargs) -> str:
    return i18n.t(key, lang, **kwargs)


# --- Help / welcome composition ---------------------------------------------


def _welcome_text(lang: str) -> str:
    parts = [
        T("welcome_title", lang),
        DIVIDER,
        "",
        T("welcome_intro", lang),
        "",
        T("welcome_signals", lang),
        T("welcome_news", lang),
        T("welcome_alerts", lang),
        "",
        THIN_DIVIDER,
        T("welcome_tip", lang),
        T("welcome_stop_hint", lang),
    ]
    return "\n".join(parts)


def _help_user_text(lang: str) -> str:
    parts = [
        T("help_user_title", lang),
        DIVIDER,
        "",
        T("help_user_section", lang),
        T("help_user_start", lang),
        T("help_user_stop", lang),
        T("help_user_news", lang),
        T("help_user_lang", lang),
        T("help_user_help", lang),
        "",
        THIN_DIVIDER,
        T("help_user_tip", lang),
    ]
    return "\n".join(parts)


def _help_admin_text(lang: str) -> str:
    parts = [
        T("help_admin_title", lang),
        DIVIDER,
        "",
        T("help_admin_user_section", lang),
        T("help_admin_user_start", lang),
        T("help_admin_user_stop", lang),
        T("help_admin_user_news", lang),
        T("help_admin_user_lang", lang),
        T("help_admin_user_help", lang),
        "",
        T("help_admin_broadcast_section", lang),
        T("help_admin_signal", lang),
        T("help_admin_broadcast", lang),
        "",
        T("help_admin_review_section", lang),
        T("help_admin_fetchnews", lang),
        T("help_admin_pending", lang),
        T("help_admin_preview", lang),
        T("help_admin_edit", lang),
        T("help_admin_approve", lang),
        T("help_admin_discard", lang),
        "",
        T("help_admin_sched_section", lang),
        T("help_admin_schedule", lang),
        T("help_admin_schedules", lang),
        T("help_admin_cancel", lang),
        "",
        T("help_admin_ops_section", lang),
        T("help_admin_stats", lang),
        T("help_admin_sendnews", lang),
        "",
        THIN_DIVIDER,
        T("help_admin_photo_title", lang),
        T("help_admin_photo_desc", lang),
        "",
        THIN_DIVIDER,
        T("help_admin_sched_examples", lang),
        "<code>/schedule 30m BTCUSDT LONG entry=65000</code>",
        "<code>/schedule 17:30</code>",
        "<code>/schedule 2026-05-06 09:00</code>",
    ]
    return "\n".join(parts)


# --- Inline keyboards --------------------------------------------------------


def _user_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Quick-action buttons shown to regular subscribers."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(T("btn_news", lang), callback_data="act:news"),
            InlineKeyboardButton(T("btn_help", lang), callback_data="act:help"),
        ],
        [
            InlineKeyboardButton(T("btn_status", lang), callback_data="act:status"),
            InlineKeyboardButton(T("btn_language", lang), callback_data="act:language"),
        ],
        [
            InlineKeyboardButton(T("btn_stop", lang), callback_data="act:stop"),
        ],
    ])


def _admin_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Quick-action buttons shown to the admin."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(T("btn_stats", lang), callback_data="act:stats"),
            InlineKeyboardButton(T("btn_schedules", lang), callback_data="act:schedules"),
        ],
        [
            InlineKeyboardButton(T("btn_fetchnews", lang), callback_data="act:fetchnews"),
            InlineKeyboardButton(T("btn_pending", lang), callback_data="act:pending"),
        ],
        [
            InlineKeyboardButton(T("btn_language", lang), callback_data="act:language"),
            InlineKeyboardButton(T("btn_help", lang), callback_data="act:help"),
        ],
    ])


def _article_review_keyboard(article_id: int, lang: str) -> InlineKeyboardMarkup:
    """Buttons attached to /preview output for one-tap actions."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(T("btn_approve", lang), callback_data=f"art:approve:{article_id}"),
        InlineKeyboardButton(T("btn_discard", lang), callback_data=f"art:discard:{article_id}"),
    ]])


def _language_picker_keyboard(current: str) -> InlineKeyboardMarkup:
    """Inline keyboard listing every supported language. The currently
    selected one is marked with ✓."""
    rows = []
    for code, name in i18n.LANGUAGES.items():
        label = f"✓ {name}" if code == current else name
        rows.append([InlineKeyboardButton(label, callback_data=f"lang:{code}")])
    return InlineKeyboardMarkup(rows)


# --- Helpers -----------------------------------------------------------------


def _is_admin(cfg: Config, user_id: int) -> bool:
    return user_id == cfg.admin_user_id


async def _send_one(
    bot,
    chat_id: int | str,
    text: str,
    *,
    photo_file_id: str | None = None,
    parse_mode: str = ParseMode.HTML,
    disable_web_page_preview: bool = False,
) -> None:
    """Send a single message — photo+caption if photo_file_id given, else text.
    If text is longer than the caption limit, sends photo with no caption then
    a follow-up text message."""
    if photo_file_id:
        if len(text) <= CAPTION_MAX:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_file_id,
                caption=text or None,
                parse_mode=parse_mode if text else None,
            )
        else:
            await bot.send_photo(chat_id=chat_id, photo=photo_file_id)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )


async def _broadcast(
    context: ContextTypes.DEFAULT_TYPE,
    cfg: Config,
    db: Database,
    text_for_lang,
    *,
    photo_file_id: str | None = None,
    parse_mode: str = ParseMode.HTML,
    disable_web_page_preview: bool = False,
) -> tuple[int, int]:
    """Send a broadcast to channel + every active subscriber.

    `text_for_lang` is either:
        • a plain str — same text for every recipient (no per-user translation), or
        • a callable lang -> str — invoked once per recipient with their language.

    Returns (delivered, failed). Removes users who blocked the bot.
    """
    delivered = 0
    failed = 0
    bot = context.bot

    if callable(text_for_lang):
        render = text_for_lang
    else:
        _fixed = text_for_lang
        def render(_lang: str, _f=_fixed) -> str:  # noqa
            return _f

    # Channel first — uses DEFAULT_LANG (one channel = one language)
    if cfg.channel_id:
        try:
            await _send_one(
                bot, cfg.channel_id, render(i18n.DEFAULT_LANG),
                photo_file_id=photo_file_id,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            delivered += 1
        except TelegramError as e:
            log.warning("Channel send failed (%s): %s", cfg.channel_id, e)
            failed += 1

    # Direct subscribers — each gets their preferred language.
    pairs = db.active_subscribers_with_language()
    throttle_every = 20 if photo_file_id else 25

    for i, (uid, lang) in enumerate(pairs):
        lang = lang if lang in i18n.LANGUAGES else i18n.DEFAULT_LANG
        try:
            await _send_one(
                bot, uid, render(lang),
                photo_file_id=photo_file_id,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            delivered += 1
        except Forbidden:
            db.remove_subscriber(uid)
            failed += 1
        except BadRequest as e:
            log.warning("BadRequest sending to %s: %s", uid, e)
            failed += 1
        except TelegramError as e:
            log.warning("TelegramError sending to %s: %s", uid, e)
            failed += 1

        if (i + 1) % throttle_every == 0:
            await asyncio.sleep(1.0)

    return delivered, failed


def _extract_photo_id(message: Message) -> str | None:
    """Return the largest photo's file_id from this message OR the message it
    replies to. Returns None if no photo is attached."""
    candidates: list[Message] = [message]
    if message.reply_to_message is not None:
        candidates.append(message.reply_to_message)

    for m in candidates:
        if m.photo:
            return m.photo[-1].file_id
    return None


def _extract_command_body(message: Message, command: str) -> str:
    """Extract everything after `/command` from either text or caption."""
    raw = message.text or message.caption or ""
    if not raw:
        return ""
    parts = raw.split(" ", 1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


# --- Command handlers --------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return

    # Resolve language BEFORE adding the subscriber so we can persist it.
    lang = _resolve_lang(db, user)

    is_new = db.add_subscriber(user.id, user.username, user.first_name)
    # Make sure the language stays bound to this user (even if they re-/start).
    db.set_user_language(user.id, lang)

    if is_new:
        text = _welcome_text(lang)
    else:
        text = T("welcome_back", lang, thin=THIN_DIVIDER)
    keyboard = _admin_keyboard(lang) if _is_admin(cfg, user.id) else _user_keyboard(lang)
    await update.effective_message.reply_html(text, reply_markup=keyboard)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    lang = _resolve_lang(db, user)
    db.remove_subscriber(user.id)
    await update.effective_message.reply_html(T("stopped", lang, thin=THIN_DIVIDER))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    lang = _resolve_lang(db, user)
    is_admin = bool(user and _is_admin(cfg, user.id))
    text = _help_admin_text(lang) if is_admin else _help_user_text(lang)
    keyboard = _admin_keyboard(lang) if is_admin else _user_keyboard(lang)
    await update.effective_message.reply_html(text, reply_markup=keyboard)


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show an inline keyboard letting the user pick their UI language."""
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    lang = _resolve_lang(db, user)
    await update.effective_message.reply_html(
        T("lang_picker_title", lang, thin=THIN_DIVIDER),
        reply_markup=_language_picker_keyboard(lang),
    )


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    body = _extract_command_body(msg, "signal")
    photo_file_id = _extract_photo_id(msg)

    if not body and not photo_file_id:
        await msg.reply_html(T("signal_usage", lang))
        return

    # Render per-recipient: only the wrapper translates; admin's typed body unchanged.
    def render(target_lang: str) -> str:
        return _format_signal(body, target_lang)

    delivered, failed = await _broadcast(
        context, cfg, db, render, photo_file_id=photo_file_id,
    )
    img = " 🖼️" if photo_file_id else ""
    await msg.reply_html(T(
        "signal_sent", lang, img=img, thin=THIN_DIVIDER,
        delivered=delivered, failed=failed,
    ))


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    body = _extract_command_body(msg, "broadcast")
    photo_file_id = _extract_photo_id(msg)

    if not body and not photo_file_id:
        await msg.reply_text(T("broadcast_usage", lang))
        return

    # Plain admin broadcast — body is admin-typed; sent as-is to all recipients.
    delivered, failed = await _broadcast(
        context, cfg, db, body, photo_file_id=photo_file_id,
    )
    img = " 🖼️" if photo_file_id else ""
    await msg.reply_html(T(
        "broadcast_sent", lang, img=img, thin=THIN_DIVIDER,
        delivered=delivered, failed=failed,
    ))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text(T("admin_only", lang))
        return

    pending: dict[str, ScheduledJob] = context.application.bot_data.get("scheduled_jobs", {})
    web_dot = "🟢" if cfg.webhook_enabled else "⚪️"
    mail_dot = "🟢" if cfg.email_bridge_enabled else "⚪️"
    chan_dot = "🟢" if cfg.channel_id else "⚪️"
    web_state = T("stats_state_on", lang) if cfg.webhook_enabled else T("stats_state_off", lang)
    mail_state = T("stats_state_on", lang) if cfg.email_bridge_enabled else T("stats_state_off", lang)
    channel_label = cfg.channel_id or T("stats_channel_none", lang)

    parts = [
        T("stats_title", lang),
        DIVIDER,
        "",
        T("stats_audience", lang),
        T("stats_subs", lang, n=db.subscriber_count()),
        T("stats_channel", lang, dot=chan_dot, ch=channel_label),
        "",
        T("stats_schedule", lang),
        T("stats_news_manual", lang),
        T("stats_pending", lang, n=len(pending)),
        "",
        T("stats_integrations", lang),
        T("stats_webhook", lang, dot=web_dot, state=web_state)
            + (f" · port {cfg.webhook_port}" if cfg.webhook_enabled else ""),
        T("stats_email", lang, dot=mail_dot, state=mail_state)
            + (f" · {cfg.imap_user}" if cfg.email_bridge_enabled else ""),
        "",
        THIN_DIVIDER,
        f"🏢 <i>{BRAND}</i>",
    ]
    text = "\n".join(parts)
    await update.effective_message.reply_html(text, reply_markup=_admin_keyboard(lang))


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand news (any user)."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    lang = _resolve_lang(db, user)
    await update.effective_message.reply_html(T("news_loading", lang))
    items = await asyncio.to_thread(fetch_news, cfg.news_sources, 10)
    if not items:
        await update.effective_message.reply_html(T("news_empty", lang))
        return
    text = _format_digest(items[: cfg.news_max_items], lang)
    await update.effective_message.reply_html(text, disable_web_page_preview=True)


async def cmd_sendnews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await update.effective_message.reply_text(T("admin_only", lang))
        return
    await update.effective_message.reply_text(T("sendnews_triggered", lang))
    await _send_news_digest(context)


def _fmt_bytes(n: int) -> str:
    """Human-friendly byte size: 12.3 KB / 4.5 MB / etc."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


async def cmd_dbstats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show database health snapshot. Admin-only."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    s = await asyncio.to_thread(db.stats)

    integrity_dot = "\U0001f7e2" if s.integrity_ok else "\U0001f534"
    integrity_label = "OK" if s.integrity_ok else "CORRUPT"
    frag = s.fragmentation_pct
    frag_dot = "\U0001f7e2" if frag < 10 else ("\U0001f7e1" if frag < 25 else "\U0001f534")

    lines = [
        "\U0001f5c4\ufe0f <b>Database health</b>",
        DIVIDER,
        "",
        "<b>\U0001f4be Storage</b>",
        f"\u251c \U0001f4c1 File size: <b>{_fmt_bytes(s.file_bytes)}</b>",
        f"\u251c \U0001f4d0 Pages: <b>{s.page_count}</b> \u00d7 {s.page_size} B",
        f"\u251c {frag_dot} Fragmentation: <b>{frag}%</b> ({s.freelist_pages} free pages)",
        f"\u2514 \u267b\ufe0f Reclaimable: <b>{_fmt_bytes(s.reclaimable_bytes)}</b>",
        "",
        "<b>\U0001f465 Subscribers</b>",
        f"\u251c \U0001f7e2 Active: <b>{s.subs_active}</b>",
        f"\u2514 \u26aa\ufe0f Inactive: <b>{s.subs_inactive}</b>",
        "",
        "<b>\U0001f4f0 News</b>",
        f"\u251c \U0001f441\ufe0f Seen (dedup): <b>{s.seen_news}</b>",
        f"\u251c \U0001f7e1 Pending: <b>{s.pending}</b>",
        f"\u251c \U0001f7e2 Approved: <b>{s.approved}</b>",
        f"\u2514 \u26ab\ufe0f Discarded: <b>{s.discarded}</b>",
        "",
        "<b>\U0001f6e1\ufe0f Integrity</b>",
        f"\u2514 {integrity_dot} <b>{integrity_label}</b>",
        "",
        THIN_DIVIDER,
        "\U0001f4a1 Tip: run <code>/dboptimize</code> to prune old rows + reclaim space.",
    ]
    if frag >= 25:
        lines.append("\u26a0\ufe0f High fragmentation \u2014 a VACUUM is recommended.")
    if not s.integrity_ok:
        lines.append("\u26a0\ufe0f <b>Integrity check FAILED.</b> Investigate before further writes.")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001f9f9 Optimize now", callback_data="db:optimize"),
        InlineKeyboardButton("\U0001f504 Refresh", callback_data="db:stats"),
    ]])
    await msg.reply_html("\n".join(lines), reply_markup=kb)


async def cmd_dboptimize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a full maintenance pass: prune + ANALYZE + VACUUM. Admin-only."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    status = await msg.reply_html("\u23f3 <b>Optimizing database\u2026</b>\nPruning old rows, running ANALYZE + VACUUM.")

    try:
        result = await asyncio.to_thread(db.optimize)
    except Exception as e:
        log.exception("DB optimize failed")
        await status.edit_text(f"\u26a0\ufe0f Optimization failed: <code>{_escape_for_html(str(e))}</code>", parse_mode=ParseMode.HTML)
        return

    freed = result["size_freed_bytes"]
    lines = [
        "\u2705 <b>Database optimized</b>",
        DIVIDER,
        "",
        "<b>\U0001f5d1\ufe0f Pruned</b>",
        f"\u251c \U0001f4f0 Old news GUIDs: <b>{result['deleted_news']}</b>",
        f"\u251c \U0001f5c2\ufe0f Old articles: <b>{result['deleted_articles']}</b>",
        f"\u2514 \U0001f465 Stale subscribers: <b>{result['deleted_subscribers']}</b>",
        "",
        "<b>\U0001f4be Storage</b>",
        f"\u251c \U0001f4c1 Before: <b>{_fmt_bytes(result['size_before_bytes'])}</b>",
        f"\u251c \U0001f4c1 After:  <b>{_fmt_bytes(result['size_after_bytes'])}</b>",
        f"\u2514 \u267b\ufe0f Freed:  <b>{_fmt_bytes(freed)}</b>",
        "",
        THIN_DIVIDER,
        f"\U0001f4cb Retention: news 30d \u00b7 articles 14d \u00b7 inactive subs 90d",
    ]
    await status.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _job_db_maintenance(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Weekly background maintenance: prune + ANALYZE (no VACUUM \u2014 too disruptive).
    Runs every 7 days from bot startup."""
    db: Database = context.application.bot_data["db"]
    cfg: Config = context.application.bot_data["cfg"]
    log.info("Weekly DB maintenance: starting")
    try:
        result = await asyncio.to_thread(
            db.optimize, do_vacuum=False,
        )
        log.info(
            "Weekly DB maintenance done: "
            "news=-%d articles=-%d subs=-%d",
            result["deleted_news"], result["deleted_articles"], result["deleted_subscribers"],
        )
        # Notify admin only if something was actually cleaned up.
        total = (
            result["deleted_news"]
            + result["deleted_articles"]
            + result["deleted_subscribers"]
        )
        if total > 0:
            try:
                await context.bot.send_message(
                    chat_id=cfg.admin_user_id,
                    text=(
                        f"\U0001f9f9 <b>Weekly DB maintenance</b>\n"
                        f"Pruned {total} old rows "
                        f"(news={result['deleted_news']}, "
                        f"articles={result['deleted_articles']}, "
                        f"subs={result['deleted_subscribers']})"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass  # don't fail the job if admin DM is unavailable
    except Exception:
        log.exception("Weekly DB maintenance FAILED")


async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the RSS feeds currently configured. Admin-only diagnostic."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return
    if not cfg.news_sources:
        await msg.reply_html("⚠️ <b>No news sources configured.</b>")
        return
    lines = [
        "📡 <b>Active news sources</b>",
        DIVIDER,
        f"🔢 {len(cfg.news_sources)} feed(s) loaded:",
        "",
    ]
    for i, url in enumerate(cfg.news_sources, 1):
        lines.append(f"  <b>{i}.</b> <code>{_escape_for_html(url)}</code>")
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(
        "ℹ️ Override via <code>NEWS_SOURCES</code> in <code>.env</code> "
        "(comma-separated). Leave empty to use Vietnamese defaults."
    )
    await msg.reply_html("\n".join(lines), disable_web_page_preview=True)


# --- News review queue ------------------------------------------------------


MAX_FETCH_PER_RUN = 12  # cap to avoid hammering source sites


async def cmd_fetchnews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pull latest headlines, scrape image + full body, store as 'pending'."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    status = await msg.reply_html(T("fetchnews_loading", lang))

    headlines = await asyncio.to_thread(fetch_news, cfg.news_sources, 6)
    headlines = headlines[:MAX_FETCH_PER_RUN]

    if not headlines:
        await status.edit_text(T("fetchnews_no_headlines", lang))
        return

    await status.edit_text(
        T("fetchnews_progress", lang, n=len(headlines)),
        parse_mode=ParseMode.HTML,
    )

    saved = 0
    skipped_dup = 0
    failed = 0
    saved_ids: list[int] = []

    for h in headlines:
        try:
            full = await asyncio.to_thread(fetch_full_article, h)
        except Exception as e:
            log.warning("Failed to scrape %s: %s", h.link, e)
            failed += 1
            continue

        published_str = full.published.isoformat() if full.published else None
        new_id = db.save_pending_article(
            guid=full.guid,
            title=full.title,
            link=full.link,
            source=full.source,
            body=full.body,
            image_url=full.image_url,
            published=published_str,
        )
        if new_id is None:
            skipped_dup += 1
        else:
            saved += 1
            saved_ids.append(new_id)

    pending_total = db.count_pending_articles()
    summary = T(
        "fetchnews_summary", lang, div=DIVIDER,
        saved=saved, dup=skipped_dup, fail=failed, total=pending_total,
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(T("btn_view_pending", lang), callback_data="act:pending"),
    ]])
    await status.edit_text(summary, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List articles awaiting review."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    items = db.list_pending_articles(limit=20)
    if not items:
        await msg.reply_html(T("pending_empty", lang))
        return

    lines = [
        T("pending_title", lang),
        DIVIDER,
        T("pending_count", lang, n=len(items)),
        "",
    ]
    for a in items:
        title = a.title if len(a.title) <= 80 else a.title[:77] + "…"
        img = " 🖼️" if a.image_url else ""
        lines.append(
            f"🔸 <b>#{a.id}</b>{img} — <i>{a.source}</i>\n"
            f"  📰 {title}"
        )
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(T("pending_legend", lang))
    await msg.reply_html("\n".join(lines))


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the article (image + full text) back to the admin for review."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    if not context.args:
        await msg.reply_text(T("preview_usage", lang))
        return

    article = await _resolve_article(db, msg, context.args[0], lang)
    if article is None:
        return

    await _send_article_preview(
        context, msg.chat_id, article,
        admin_lang=lang,
        header=T("preview_header", lang),
    )


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replace the body of a pending article. Usage: /edit <id> <new text>"""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    raw = _extract_command_body(msg, "edit")
    parts = raw.split(None, 1)
    if len(parts) < 2:
        await msg.reply_html(T("edit_usage", lang))
        return

    article = await _resolve_article(db, msg, parts[0], lang)
    if article is None:
        return
    if article.status != "pending":
        await msg.reply_html(T(
            "article_already_status", lang,
            id=article.id, status=_status_label(article.status, lang),
        ))
        return

    new_body = parts[1].strip()
    if not new_body:
        await msg.reply_text(T("empty_body", lang))
        return

    db.update_article_body(article.id, new_body)
    await msg.reply_html(T(
        "article_updated", lang,
        id=article.id, thin=THIN_DIVIDER, n=len(new_body),
    ))


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a pending article to channel + subscribers."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    if not context.args:
        await msg.reply_text(T("approve_usage", lang))
        return

    article = await _resolve_article(db, msg, context.args[0], lang)
    if article is None:
        return
    if article.status == "approved":
        await msg.reply_html(T("article_already_approved", lang, id=article.id))
        return
    if article.status == "discarded":
        await msg.reply_html(T("article_already_discarded", lang, id=article.id))
        return

    # Article body stays in source language; only the wrapper translates.
    def render(target_lang: str) -> str:
        return _format_article_for_broadcast(article, target_lang)

    delivered, failed = await _broadcast_with_photo_url(
        context, cfg, db, render, photo_url=article.image_url,
    )
    db.set_article_status(article.id, "approved")

    await msg.reply_html(T(
        "article_broadcast_done", lang,
        id=article.id, thin=THIN_DIVIDER,
        delivered=delivered, failed=failed,
        left=db.count_pending_articles(),
    ))


async def cmd_discard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove an article from the pending queue."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    if not context.args:
        await msg.reply_text(T("discard_usage", lang))
        return

    article = await _resolve_article(db, msg, context.args[0], lang)
    if article is None:
        return

    db.set_article_status(article.id, "discarded")
    await msg.reply_html(T(
        "article_discarded", lang,
        id=article.id, left=db.count_pending_articles(),
    ))


# --- News review helpers ----------------------------------------------------


def _status_label(status: str, lang: str) -> str:
    """Translate an article status code into the user's language."""
    return T(f"article_status_{status}", lang)


async def _resolve_article(db: Database, msg: Message, raw_id: str, lang: str):
    """Parse an article id from user input. Returns the article or None
    (after replying with an error message)."""
    try:
        article_id = int(raw_id.lstrip("#"))
    except ValueError:
        await msg.reply_text(T("article_invalid_id", lang, raw=raw_id))
        return None
    article = db.get_pending_article(article_id)
    if article is None:
        await msg.reply_html(T("article_not_found", lang, id=article_id))
        return None
    return article


def _format_article_for_broadcast(article, lang: str) -> str:
    """Format a stored article as the message that goes to subscribers.

    The body and title stay in the original (source) language; only the
    surrounding wrapper (link label) is translated.
    """
    title = _escape_for_html(article.title)
    source = _escape_for_html(article.source)
    body = _escape_for_html(article.body)
    # Telegram message body cap is 4096 chars; cap body so the whole message fits.
    header_footer_overhead = 400
    max_body = 4096 - header_footer_overhead
    if len(body) > max_body:
        body = body[: max_body - 1].rstrip() + "…"
    read_label = T("article_read_on", lang, source=source)
    return (
        f"📰 <b>{title}</b>\n"
        f"{DIVIDER}\n\n"
        f"{body}\n\n"
        f"{THIN_DIVIDER}\n"
        f"🔗 <a href=\"{_escape_for_html(article.link)}\">{read_label}</a>\n"
        f"🏢 <i>{BRAND}</i>"
    )


def _escape_for_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def _send_article_preview(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    article,
    admin_lang: str,
    header: str | None = None,
) -> None:
    """Send the admin a preview: image (if any) + caption (or follow-up text)."""
    if header is None:
        header = T("preview_header", admin_lang)
    body_text = _format_article_for_broadcast(article, admin_lang)
    preview_header = (
        T("preview_label", admin_lang, header=header, id=article.id)
        + f"\n{THIN_DIVIDER}\n"
    )
    full_text = preview_header + body_text
    kb = _article_review_keyboard(article.id, admin_lang)

    if article.image_url:
        try:
            if len(full_text) <= CAPTION_MAX:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=article.image_url,
                    caption=full_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                return
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=article.image_url,
                )
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=full_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
                return
        except TelegramError as e:
            log.warning("Photo preview failed for article %s: %s", article.id, e)

    # No image (or photo send failed) — send text only
    await context.bot.send_message(
        chat_id=chat_id,
        text=full_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=kb,
    )


async def _broadcast_with_photo_url(
    context,
    cfg: Config,
    db: Database,
    text_for_lang,
    *,
    photo_url: str | None,
) -> tuple[int, int]:
    """Like _broadcast() but accepts an HTTP photo URL instead of a Telegram file_id.

    `text_for_lang` is either a plain str (same text for everyone) or a
    callable lang -> str (per-recipient translation).
    """
    delivered = 0
    failed = 0
    bot = context.bot

    if callable(text_for_lang):
        render = text_for_lang
    else:
        _fixed = text_for_lang
        def render(_lang: str, _f=_fixed) -> str:  # noqa
            return _f

    async def send(target, lang: str):
        body_text = render(lang)
        if photo_url:
            try:
                if len(body_text) <= CAPTION_MAX:
                    await bot.send_photo(
                        chat_id=target,
                        photo=photo_url,
                        caption=body_text,
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await bot.send_photo(chat_id=target, photo=photo_url)
                    await bot.send_message(
                        chat_id=target,
                        text=body_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                return
            except (BadRequest, TelegramError) as e:
                log.warning("Photo URL send failed for %s, falling back to text: %s", target, e)
        await bot.send_message(
            chat_id=target,
            text=body_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    if cfg.channel_id:
        try:
            await send(cfg.channel_id, i18n.DEFAULT_LANG)
            delivered += 1
        except TelegramError as e:
            log.warning("Channel send failed: %s", e)
            failed += 1

    pairs = db.active_subscribers_with_language()
    throttle_every = 18 if photo_url else 25
    for i, (uid, lang) in enumerate(pairs):
        lang = lang if lang in i18n.LANGUAGES else i18n.DEFAULT_LANG
        try:
            await send(uid, lang)
            delivered += 1
        except Forbidden:
            db.remove_subscriber(uid)
            failed += 1
        except TelegramError as e:
            log.warning("Send to %s failed: %s", uid, e)
            failed += 1
        if (i + 1) % throttle_every == 0:
            await asyncio.sleep(1.0)

    return delivered, failed


# --- Scheduled broadcast commands -------------------------------------------


def _kind_label(kind: str, lang: str) -> str:
    return T(f"kind_{kind}", lang)


async def _fire_scheduled_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback that runs when a scheduled broadcast is due."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    pending: dict[str, ScheduledJob] = context.application.bot_data["scheduled_jobs"]

    job_data: ScheduledJob = context.job.data
    pending.pop(job_data.job_id, None)

    if job_data.kind == "signal":
        def render(target_lang: str) -> str:
            return _format_signal(job_data.body, target_lang)
    else:
        # Plain admin-typed broadcast — same text for everyone.
        def render(_target_lang: str, _b=job_data.body) -> str:  # noqa
            return _b

    delivered, failed = await _broadcast(
        context, cfg, db, render, photo_file_id=job_data.photo_file_id,
    )
    log.info(
        "Scheduled %s '%s' fired: delivered=%d failed=%d",
        job_data.kind, job_data.job_id, delivered, failed,
    )

    # Notify admin in the admin's preferred language.
    admin_lang = db.get_user_language(job_data.created_by) or i18n.DEFAULT_LANG
    if admin_lang not in i18n.LANGUAGES:
        admin_lang = i18n.DEFAULT_LANG
    try:
        suffix = T("with_image_suffix", admin_lang) if job_data.photo_file_id else ""
        await context.bot.send_message(
            chat_id=job_data.created_by,
            text=T(
                "scheduled_fire_notice", admin_lang,
                kind=_kind_label(job_data.kind, admin_lang),
                id=job_data.job_id, suffix=suffix,
                delivered=delivered, failed=failed,
            ),
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as e:
        log.warning("Could not notify admin of scheduled fire: %s", e)


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    msg = update.effective_message
    user = update.effective_user
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    raw = _extract_command_body(msg, "schedule")
    photo_file_id = _extract_photo_id(msg)

    if not raw:
        await msg.reply_html(T("schedule_usage", lang))
        return

    when_str, body = split_when_and_body(raw)
    if not body:
        await msg.reply_text(T("schedule_no_body", lang))
        return

    tz = ZoneInfo(cfg.timezone)
    try:
        fire_at = parse_when(when_str, tz)
    except TimerError as e:
        await msg.reply_text("⚠️ " + T(e.key, lang, **e.fmt))
        return

    # Decide signal vs plain broadcast
    kind = "broadcast"
    cleaned_body = body
    if body.lower().startswith("signal:"):
        kind = "signal"
        cleaned_body = body.split(":", 1)[1].strip()
        if not cleaned_body:
            await msg.reply_text(T("schedule_empty_signal", lang))
            return

    job_id = uuid.uuid4().hex[:8]
    sjob = ScheduledJob(
        job_id=job_id,
        kind=kind,
        body=cleaned_body,
        photo_file_id=photo_file_id,
        fire_at=fire_at,
        created_by=user.id,
    )

    pending: dict[str, ScheduledJob] = context.application.bot_data["scheduled_jobs"]
    pending[job_id] = sjob

    context.application.job_queue.run_once(
        _fire_scheduled_job,
        when=fire_at,
        data=sjob,
        name=f"sched_{job_id}",
    )

    img_note = " 🖼️" if photo_file_id else ""
    preview = cleaned_body if len(cleaned_body) <= 120 else cleaned_body[:117] + "…"
    kind_icon = "📈" if kind == "signal" else "📢"
    cancel_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(T("btn_cancel_job", lang, job_id=job_id), callback_data=f"cancel:{job_id}"),
        InlineKeyboardButton(T("btn_all_schedules", lang), callback_data="act:schedules"),
    ]])
    await msg.reply_html(
        T(
            "schedule_created", lang,
            img=img_note, div=DIVIDER, id=job_id,
            icon=kind_icon, kind=_kind_label(kind, lang),
            when=sjob.human_time(), preview=preview,
        ),
        reply_markup=cancel_kb,
    )


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    pending: dict[str, ScheduledJob] = context.application.bot_data["scheduled_jobs"]
    if not pending:
        await msg.reply_text(T("schedules_empty", lang))
        return

    items = sorted(pending.values(), key=lambda j: j.fire_at)
    lines = [
        T("schedules_title", lang),
        DIVIDER,
        T("schedules_count", lang, n=len(items)),
        "",
    ]
    for j in items:
        img = " 🖼️" if j.photo_file_id else ""
        kind_icon = "📈" if j.kind == "signal" else "📢"
        preview = j.body if len(j.body) <= 60 else j.body[:57] + "…"
        lines.append(
            f"{kind_icon} <code>{j.job_id}</code>{img}\n"
            f"  ⏱ <b>{j.human_time()}</b>\n"
            f"  📝 <i>{preview}</i>"
        )
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(T("schedules_hint", lang))

    # Inline cancel buttons (max 5 to avoid clutter)
    rows = []
    for j in items[:5]:
        rows.append([InlineKeyboardButton(
            T("btn_cancel_job", lang, job_id=j.job_id),
            callback_data=f"cancel:{j.job_id}",
        )])
    kb = InlineKeyboardMarkup(rows) if rows else None
    await msg.reply_html("\n".join(lines), reply_markup=kb)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    msg = update.effective_message
    lang = _resolve_lang(db, user)
    if user is None or not _is_admin(cfg, user.id):
        await msg.reply_text(T("admin_only", lang))
        return

    if not context.args:
        await msg.reply_text(T("cancel_usage", lang))
        return

    job_id = context.args[0].strip()
    pending: dict[str, ScheduledJob] = context.application.bot_data["scheduled_jobs"]
    if job_id not in pending:
        await msg.reply_text(T("cancel_not_found", lang, id=job_id))
        return

    # Find and remove the JobQueue job
    jq_jobs = context.application.job_queue.get_jobs_by_name(f"sched_{job_id}")
    for j in jq_jobs:
        j.schedule_removal()
    pending.pop(job_id, None)

    await msg.reply_html(T("cancel_done", lang, thin=THIN_DIVIDER, id=job_id))


# --- Photo-with-caption handler ---------------------------------------------


async def on_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None or not _is_admin(cfg, user.id):
        return
    caption = (msg.caption or "").strip()
    if not caption:
        return
    head = caption.split(" ", 1)[0].lower().lstrip("/")
    head = head.split("@", 1)[0]
    if head == "signal":
        await cmd_signal(update, context)
    elif head == "broadcast":
        await cmd_broadcast(update, context)
    elif head == "schedule":
        await cmd_schedule(update, context)


# --- Inline button callback handler -----------------------------------------


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch inline-keyboard button taps to the right command."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]
    query = update.callback_query
    if query is None:
        return
    await query.answer()  # acknowledge tap (removes the loading spinner)

    data = query.data or ""
    user = query.from_user
    lang = _resolve_lang(db, user)
    is_admin = bool(user and _is_admin(cfg, user.id))

    # lang:<code>  - language picker
    if data.startswith("lang:"):
        new_code = data.split(":", 1)[1]
        if new_code not in i18n.LANGUAGES:
            await query.message.reply_text(T("action_unavailable", lang))
            return
        if user is not None:
            db.set_user_language(user.id, new_code)
        name = i18n.LANGUAGES[new_code]
        await query.message.reply_html(T("lang_changed", new_code, name=name))
        return

    # act:<name>  - quick actions from menus
    if data.startswith("act:"):
        action = data.split(":", 1)[1]
        if action == "news":
            await cmd_news(update, context)
        elif action == "help":
            await cmd_help(update, context)
        elif action == "language":
            await cmd_language(update, context)
        elif action == "status":
            await query.message.reply_html(T("bot_online", lang, thin=THIN_DIVIDER))
        elif action == "stop":
            await cmd_stop(update, context)
        elif action == "stats" and is_admin:
            await cmd_stats(update, context)
        elif action == "schedules" and is_admin:
            await cmd_schedules(update, context)
        elif action == "sendnews" and is_admin:
            await query.message.reply_html(T("news_loading", lang))
            await _send_news_digest(context)
        elif action == "fetchnews" and is_admin:
            await cmd_fetchnews(update, context)
        elif action == "pending" and is_admin:
            await cmd_pending(update, context)
        else:
            await query.message.reply_text(T("action_unavailable", lang))
        return

    # db:<stats|optimize>  - admin database maintenance buttons
    if data.startswith("db:") and is_admin:
        action = data.split(":", 1)[1]
        if action == "stats":
            await cmd_dbstats(update, context)
        elif action == "optimize":
            await cmd_dboptimize(update, context)
        else:
            await query.message.reply_text(T("action_unavailable", lang))
        return

    # art:<approve|discard>:<id>  - one-tap article actions from preview
    if data.startswith("art:") and is_admin:
        try:
            _, action, raw_id = data.split(":", 2)
            article_id = int(raw_id)
        except ValueError:
            await query.message.reply_text(T("article_bad_button", lang))
            return
        article = db.get_pending_article(article_id)
        if article is None:
            await query.message.reply_html(T("article_gone", lang, id=article_id))
            return

        if action == "approve":
            if article.status != "pending":
                await query.message.reply_html(T(
                    "article_already_short", lang,
                    id=article.id, status=_status_label(article.status, lang),
                ))
                return

            def render(target_lang: str) -> str:
                return _format_article_for_broadcast(article, target_lang)

            delivered, failed = await _broadcast_with_photo_url(
                context, cfg, db, render, photo_url=article.image_url,
            )
            db.set_article_status(article.id, "approved")
            await query.message.reply_html(T(
                "article_broadcast_short", lang,
                id=article.id, thin=THIN_DIVIDER,
                delivered=delivered, failed=failed,
            ))
            return

        if action == "discard":
            db.set_article_status(article.id, "discarded")
            await query.message.reply_html(T(
                "article_discarded_short", lang, id=article.id,
            ))
            return

    # cancel:<job_id>  - cancel a scheduled job from inline button
    if data.startswith("cancel:") and is_admin:
        job_id = data.split(":", 1)[1]
        pending: dict[str, ScheduledJob] = context.application.bot_data["scheduled_jobs"]
        if job_id not in pending:
            await query.message.reply_html(T("cancel_done_btn", lang, id=job_id))
            return
        for j in context.application.job_queue.get_jobs_by_name(f"sched_{job_id}"):
            j.schedule_removal()
        pending.pop(job_id, None)
        await query.message.reply_html(T("cancel_done", lang, thin=THIN_DIVIDER, id=job_id))
        return


# --- Scheduled job -----------------------------------------------------------


def _format_signal(body: str, lang: str) -> str:
    """Format a trading signal into the styled card sent to subscribers.

    Only the wrapper translates per recipient; the admin-typed `body` is
    sent verbatim.
    """
    return (
        T("signal_card_title", lang) + "\n"
        f"{DIVIDER}\n"
        f"{body}\n"
        f"{DIVIDER}\n"
        + T("signal_disclaimer", lang) + "\n"
        f"🏢 <i>{BRAND}</i>"
    )


def _format_digest(items: list[NewsItem], lang: str) -> str:
    lines = [
        T("digest_title", lang),
        DIVIDER,
        T("digest_count", lang, n=len(items)),
        "",
    ]
    lines.extend(item.render() for item in items)
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(T("digest_sources", lang))
    lines.append(f"🏢 <i>{BRAND}</i>")
    return "\n".join(lines)


async def _send_news_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Build and broadcast a news digest. Triggered manually only —
    via /sendnews or the inline news button."""
    cfg: Config = context.application.bot_data["cfg"]
    db: Database = context.application.bot_data["db"]

    items = await asyncio.to_thread(fetch_news, cfg.news_sources, 15)

    fresh = [i for i in items if not db.is_news_seen(i.guid)]
    if not fresh:
        log.info("News digest: nothing new to send")
        return

    digest_items = fresh[: cfg.news_max_items]

    # Each subscriber gets the digest with their preferred wrapper language.
    def render(target_lang: str) -> str:
        return _format_digest(digest_items, target_lang)

    delivered, failed = await _broadcast(
        context, cfg, db, render, disable_web_page_preview=True,
    )
    log.info("News digest sent. Delivered=%d failed=%d", delivered, failed)

    for it in digest_items:
        db.mark_news_seen(it.guid)
    db.prune_old_news(30)


# --- Setup -------------------------------------------------------------------


async def _post_init(application: Application) -> None:
    # Register per-language command descriptions so Telegram's "/" menu
    # shows native text for each user's chosen client language.
    base_cmds = [
        ("start", "cmd_start_desc"),
        ("stop", "cmd_stop_desc"),
        ("news", "cmd_news_desc"),
        ("language", "cmd_language_desc"),
        ("help", "cmd_help_desc"),
    ]
    # Default (no language_code) — DEFAULT_LANG
    await application.bot.set_my_commands([
        BotCommand(name, T(key, i18n.DEFAULT_LANG)) for name, key in base_cmds
    ])
    # Per-language overrides
    for code in i18n.LANGUAGES:
        try:
            await application.bot.set_my_commands(
                [BotCommand(name, T(key, code)) for name, key in base_cmds],
                language_code=code,
            )
        except TelegramError as e:
            log.warning("set_my_commands(%s) failed: %s", code, e)
    log.info("Bot commands registered (multi-language).")

    cfg: Config = application.bot_data["cfg"]
    db: Database = application.bot_data["db"]

    async def on_external_signal(html: str) -> None:
        """Broadcast a pre-formatted HTML signal from webhook or email bridge."""
        class _Ctx:
            bot = application.bot
        delivered, failed = await _broadcast(_Ctx(), cfg, db, html)
        log.info("External signal broadcast: delivered=%d failed=%d", delivered, failed)

    if cfg.webhook_enabled:
        api = webhook_mod.build_app(secret=cfg.webhook_secret, on_signal=on_external_signal)
        application.bot_data["webhook_task"] = asyncio.create_task(
            webhook_mod.serve(api, host=cfg.webhook_host, port=cfg.webhook_port),
            name="webhook-server",
        )

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
    app.bot_data["scheduled_jobs"] = {}  # job_id -> ScheduledJob

    # Public
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("language", cmd_language))
    # Admin (text or reply-to-photo)
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("schedules", cmd_schedules))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("sendnews", cmd_sendnews))
    app.add_handler(CommandHandler("sources", cmd_sources))
    # Database maintenance
    app.add_handler(CommandHandler("dbstats", cmd_dbstats))
    app.add_handler(CommandHandler("dboptimize", cmd_dboptimize))
    # News review queue
    app.add_handler(CommandHandler("fetchnews", cmd_fetchnews))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("edit", cmd_edit))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("discard", cmd_discard))
    # Photo with command in caption — must come AFTER CommandHandlers
    app.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, on_photo_caption))
    # Inline keyboard button callbacks
    app.add_handler(CallbackQueryHandler(on_button))

    # News digest is manual-only as of v3.1.0 — no scheduled job.
    # Use /sendnews or the inline news button to trigger a broadcast.
    log.info("News digest mode: manual only (no auto-schedule)")
    log.info(
        "News sources (%d): %s",
        len(cfg.news_sources),
        ", ".join(cfg.news_sources) if cfg.news_sources else "(none)",
    )

    # Weekly DB maintenance (prune + ANALYZE, no VACUUM).
    # Fires 24h after start, then every 7 days.
    app.job_queue.run_repeating(
        _job_db_maintenance,
        interval=7 * 24 * 3600,
        first=24 * 3600,
        name="db_maintenance",
    )
    log.info("Scheduled weekly DB maintenance (prune + ANALYZE)")

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
