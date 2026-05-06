"""Internationalization (i18n) module.

Per-user language is stored in the subscribers table. UI strings are looked up
in TRANSLATIONS by (lang, key). All formatting variables are passed via .format().

To add a new language:
    1) Add its code to LANGUAGES (e.g. "ko": "한국어")
    2) Add a {key: text} dict for it inside TRANSLATIONS
    3) Optionally extend LANG_CODE_MAP for Telegram language_code auto-detection

Missing keys fall back to English. Missing English keys return the key itself
(useful during development to spot gaps).
"""
from __future__ import annotations

# Code -> human label shown in /language picker
LANGUAGES: dict[str, str] = {
    "en": "🇬🇧 English",
    "vi": "🇻🇳 Tiếng Việt",
    "ja": "🇯🇵 日本語",
}

DEFAULT_LANG = "vi"  # IS6FX Vietnam — default for unknown users

# Telegram sends language_code like "en", "en-US", "vi", "ja-JP" — normalize them.
LANG_CODE_MAP: dict[str, str] = {
    "en": "en", "en-us": "en", "en-gb": "en",
    "vi": "vi", "vi-vn": "vi",
    "ja": "ja", "ja-jp": "ja",
}


def normalize(code: str | None) -> str:
    """Return a supported language code derived from a Telegram language_code,
    or DEFAULT_LANG if the input is unknown."""
    if not code:
        return DEFAULT_LANG
    c = code.lower()
    if c in LANGUAGES:
        return c
    if c in LANG_CODE_MAP:
        return LANG_CODE_MAP[c]
    # Try the bare prefix ("en-au" -> "en")
    prefix = c.split("-", 1)[0]
    return prefix if prefix in LANGUAGES else DEFAULT_LANG


# --- Translation tables ------------------------------------------------------
#
# Strings use {var} placeholders that are substituted via str.format(**kwargs).
# All strings are plain text or Telegram HTML — no Markdown.

TRANSLATIONS: dict[str, dict[str, str]] = {
    # =========================================================================
    # ENGLISH
    # =========================================================================
    "en": {
        # Bot command descriptions (shown in Telegram's "/" menu)
        "cmd_start_desc": "Subscribe to signals + news",
        "cmd_stop_desc": "Unsubscribe",
        "cmd_news_desc": "Get latest news",
        "cmd_help_desc": "Show help",
        "cmd_language_desc": "Change language",

        # Welcome / start
        "welcome_title": "✨ <b>Welcome to IS6FX Signals</b> ✨",
        "welcome_intro": "🎉 You're all set! You're now subscribed to:",
        "welcome_signals": "📈  <b>Trading Signals</b>  — real-time entries",
        "welcome_news": "📰  <b>Daily News Digest</b>  — every morning at 07:30",
        "welcome_alerts": "🔔  <b>Market Alerts</b>  — when it matters",
        "welcome_tip": "💡 <i>Tap a button below to get started.</i>",
        "welcome_stop_hint": "🛑 <i>Use /stop anytime to unsubscribe.</i>",
        "welcome_back": "✅ <b>Welcome back!</b>\n{thin}\nYou're still subscribed and ready to receive signals.",
        "stopped": "🛑 <b>Unsubscribed</b>\n{thin}\nYou won't receive any more signals or news.\n👋 <i>Send /start anytime to come back.</i>",

        # Help — user
        "help_user_title": "🧭 <b>IS6FX Signals — Help</b>",
        "help_user_section": "<b>👤 Your Commands</b>",
        "help_user_start": "├ 🟢 /start — subscribe to signals + news",
        "help_user_stop": "├ 🔴 /stop — unsubscribe",
        "help_user_news": "├ 📰 /news — get latest market news",
        "help_user_lang": "├ 🌐 /language — change language",
        "help_user_help": "└ ❓ /help — show this menu",
        "help_user_tip": "💬 <i>Tip: tap any button below for quick access.</i>",

        # Help — admin
        "help_admin_title": "🛡️ <b>IS6FX Signals — Admin Console</b>",
        "help_admin_user_section": "<b>👤 User Commands</b>",
        "help_admin_user_start": "├ 🟢 /start — subscribe",
        "help_admin_user_stop": "├ 🔴 /stop — unsubscribe",
        "help_admin_user_news": "├ 📰 /news — latest news",
        "help_admin_user_lang": "├ 🌐 /language — change language",
        "help_admin_user_help": "└ ❓ /help — this menu",
        "help_admin_broadcast_section": "<b>⚡ Broadcast</b>",
        "help_admin_signal": "├ 📈 /signal &lt;text&gt; — send a trading signal",
        "help_admin_broadcast": "└ 📢 /broadcast &lt;text&gt; — send any message",
        "help_admin_review_section": "<b>📰 News Review</b>",
        "help_admin_fetchnews": "├ 🔍 /fetchnews — pull latest articles into queue",
        "help_admin_pending": "├ 📑 /pending — list articles awaiting review",
        "help_admin_preview": "├ 👁️ /preview &lt;id&gt; — see image + full text",
        "help_admin_edit": "├ ✏️ /edit &lt;id&gt; &lt;new text&gt; — modify before sending",
        "help_admin_approve": "├ ✅ /approve &lt;id&gt; — broadcast to channel + subs",
        "help_admin_discard": "└ 🗑️ /discard &lt;id&gt; — remove from queue",
        "help_admin_sched_section": "<b>⏰ Scheduling</b>",
        "help_admin_schedule": "├ 📅 /schedule &lt;when&gt; &lt;text&gt; — future broadcast",
        "help_admin_schedules": "├ 📄 /schedules — list pending",
        "help_admin_cancel": "└ 🗑️ /cancel &lt;id&gt; — cancel a job",
        "help_admin_ops_section": "<b>🔧 Operations</b>",
        "help_admin_stats": "├ 📊 /stats — system status",
        "help_admin_sendnews": "└ 🔄 /sendnews — trigger news now",
        "help_admin_photo_title": "📸 <b>Photo support</b>",
        "help_admin_photo_desc": "<i>Attach a photo and put /signal, /broadcast or /schedule in the caption to include an image.</i>",
        "help_admin_sched_examples": "📝 <b>Schedule examples</b>",

        # Buttons
        "btn_news": "📰 Latest News",
        "btn_help": "❓ Help",
        "btn_status": "🔔 Status",
        "btn_stop": "🛑 Unsubscribe",
        "btn_language": "🌐 Language",
        "btn_stats": "📊 Stats",
        "btn_schedules": "📄 Schedules",
        "btn_fetchnews": "🔍 Fetch News",
        "btn_pending": "📑 Pending",
        "btn_approve": "✅ Approve",
        "btn_discard": "🗑️ Discard",
        "btn_view_pending": "📑 View Pending",
        "btn_cancel_job": "🗑️ Cancel {job_id}",
        "btn_all_schedules": "📄 All Schedules",

        # Common short
        "admin_only": "⛔ This command is for admins only.",
        "empty_body": "⚠️ Empty body.",
        "action_unavailable": "⛔ Action not available.",
        "bot_online": "🟢 <b>Bot is online</b>\n{thin}\nYou will receive signals and the daily news digest.",

        # Signal & broadcast
        "signal_usage": "<b>Usage:</b>\n<code>/signal BTCUSDT LONG entry=65000 sl=64000 tp=67000</code>\n\n<b>With image:</b> attach a photo and put your /signal text in the caption,\nor reply to an existing photo with <code>/signal &lt;text&gt;</code>.",
        "broadcast_usage": "Usage: /broadcast <message>\nWith image: attach a photo and put /broadcast <text> in its caption,\nor reply to a photo with /broadcast <text>.",
        "signal_sent": "✅ <b>Signal sent</b>{img}\n{thin}\n📤 Delivered: <b>{delivered}</b>\n⚠️ Failed: <b>{failed}</b>",
        "broadcast_sent": "✅ <b>Broadcast sent</b>{img}\n{thin}\n📤 Delivered: <b>{delivered}</b>\n⚠️ Failed: <b>{failed}</b>",
        "signal_card_title": "📈 <b>TRADING SIGNAL</b>  •  🆕",
        "signal_disclaimer": "⚠️ <i>Not financial advice. Trade at your own risk.</i>",

        # News digest
        "digest_title": "📰 <b>Daily Market Digest</b>",
        "digest_count": "🗞️ <b>{n}</b> top stories this morning",
        "digest_sources": "🔗 <i>Sources: CafeF • VnExpress • Vietstock</i>",
        "news_loading": "🔄 <i>Fetching latest market news…</i>",
        "news_empty": "💭 <b>No fresh news right now.</b>\n<i>Try again in a few minutes.</i>",
        "sendnews_triggered": "Triggering daily digest now…",

        # Stats / dashboard
        "stats_title": "📊 <b>System Dashboard</b>",
        "stats_audience": "<b>👥 Audience</b>",
        "stats_subs": "├ 🟢 Active subscribers: <b>{n}</b>",
        "stats_channel": "└ {dot} Channel: <code>{ch}</code>",
        "stats_channel_none": "not configured",
        "stats_schedule": "<b>⏰ Schedule</b>",
        "stats_daily": "├ 📅 Daily news: <b>{time}</b> ({tz})",
        "stats_pending": "└ 🕒 Pending jobs: <b>{n}</b>",
        "stats_integrations": "<b>🔌 Integrations</b>",
        "stats_webhook": "├ {dot} Webhook: <b>{state}</b>",
        "stats_email": "└ {dot} Email bridge: <b>{state}</b>",
        "stats_state_on": "ON",
        "stats_state_off": "OFF",

        # News review queue
        "fetchnews_loading": "🔍 <i>Fetching headlines…</i>",
        "fetchnews_no_headlines": "⚠️ No headlines returned. Check NEWS_SOURCES in .env.",
        "fetchnews_progress": "🔍 Found <b>{n}</b> headlines.\n📄 <i>Scraping article bodies + images…</i>",
        "fetchnews_summary": "✅ <b>Fetch complete</b>\n{div}\n├ 📅 New articles saved: <b>{saved}</b>\n├ 🔁 Duplicates skipped: <b>{dup}</b>\n├ ⚠️ Scrape failures: <b>{fail}</b>\n└ 📑 Total pending: <b>{total}</b>\n\n<i>Use /pending to review.</i>",
        "pending_empty": "💭 <b>No pending articles.</b>\n<i>Run /fetchnews to pull the latest.</i>",
        "pending_title": "📑 <b>Pending Articles</b>",
        "pending_count": "📊 <b>{n}</b> awaiting review",
        "pending_legend": "👁️ /preview &lt;id&gt; · ✏️ /edit &lt;id&gt; · ✅ /approve &lt;id&gt; · 🗑️ /discard &lt;id&gt;",
        "preview_usage": "Usage: /preview <id>",
        "approve_usage": "Usage: /approve <id>",
        "discard_usage": "Usage: /discard <id>",
        "edit_usage": "<b>Usage:</b> <code>/edit &lt;id&gt; &lt;new text&gt;</code>\n<i>Replaces the article body. Title and image are kept.</i>",
        "article_invalid_id": "⚠️ Invalid id: {raw}",
        "article_not_found": "⚠️ No article with id <code>#{id}</code>.",
        "article_already_status": "⚠️ Article #{id} is already <b>{status}</b> — cannot edit.",
        "article_already_approved": "⚠️ Article #{id} was already approved.",
        "article_already_discarded": "⚠️ Article #{id} was discarded.",
        "article_updated": "✏️ <b>Article #{id} updated</b>\n{thin}\nNew length: <b>{n}</b> chars.\n<i>Use /preview {id} to verify, then /approve {id}.</i>",
        "article_broadcast_done": "✅ <b>Article #{id} broadcast</b>\n{thin}\n📤 Delivered: <b>{delivered}</b>\n⚠️ Failed: <b>{failed}</b>\n📑 Pending left: <b>{left}</b>",
        "article_broadcast_short": "✅ <b>Article #{id} broadcast</b>\n{thin}\n📤 Delivered: <b>{delivered}</b>\n⚠️ Failed: <b>{failed}</b>",
        "article_discarded": "🗑️ <b>Article #{id} discarded.</b>\n📑 Pending left: <b>{left}</b>",
        "article_discarded_short": "🗑️ Article #{id} discarded.",
        "article_gone": "⚠️ Article <code>#{id}</code> no longer exists.",
        "article_already_short": "⚠️ Article #{id} is already <b>{status}</b>.",
        "article_bad_button": "⚠️ Bad button data.",
        "article_status_pending": "pending",
        "article_status_approved": "approved",
        "article_status_discarded": "discarded",
        "article_read_on": "Read on {source}",
        "preview_header": "PREVIEW",
        "preview_label": "🔎 <b>{header}</b>  ·  ID <code>#{id}</code>",

        # Scheduler
        "schedule_usage": "<b>Usage:</b>\n<code>/schedule &lt;when&gt; &lt;message&gt;</code>\n\n<b>Examples</b>\n<code>/schedule 30m BTCUSDT LONG entry=65000</code>\n<code>/schedule 17:30 EU session opening</code>\n<code>/schedule 2026-05-06 09:00 NFP reminder</code>\n\nAdd <code>signal:</code> at the start to format as a trading signal:\n<code>/schedule 1h signal: BTCUSDT LONG entry=65000 sl=64000</code>\n\nAttach a photo with the caption to include an image.",
        "schedule_no_body": "⚠️ You provided a time but no message body.",
        "schedule_empty_signal": "⚠️ Empty signal body after `signal:`.",
        "schedule_created": "⏰ <b>Scheduled</b>{img}\n{div}\n├ 🆔 ID: <code>{id}</code>\n├ {icon} Type: <b>{kind}</b>\n├ 📅 Fires at: <b>{when}</b>\n└ 📝 Preview: <i>{preview}</i>",
        "schedules_empty": "No scheduled broadcasts.",
        "schedules_title": "⏰ <b>Scheduled Broadcasts</b>",
        "schedules_count": "📊 <b>{n}</b> pending",
        "schedules_hint": "🗑️ <i>Cancel any job:</i> <code>/cancel &lt;id&gt;</code>",
        "cancel_usage": "Usage: /cancel <id>   (get IDs from /schedules)",
        "cancel_not_found": "⚠️ No pending job with id `{id}`.",
        "cancel_done": "🗑️ <b>Cancelled</b>\n{thin}\nJob <code>{id}</code> was removed from the queue.",
        "cancel_done_btn": "⚠️ Job <code>{id}</code> not found (already fired or cancelled).",
        "scheduled_fire_notice": "⏰ Scheduled {kind} <code>{id}</code> sent{suffix}.\nDelivered: {delivered}, failed: {failed}",
        "with_image_suffix": " 🖼️ with image",
        "kind_signal": "signal",
        "kind_broadcast": "broadcast",

        # Scheduler errors (raised from app/scheduler.py)
        "err_empty_time": "Empty time. Try `30m` or `17:30`.",
        "err_duration_zero": "Duration must be greater than zero.",
        "err_duration_too_long": "Duration too long (max 30 days).",
        "err_in_past": "Time {when} is already in the past.",
        "err_unknown_time": "Could not understand time. Examples: `30m`, `2h`, `1d12h`, `17:30`, `2026-05-06 09:00`.",

        # Language picker
        "lang_picker_title": "🌐 <b>Choose your language</b>\n{thin}\n<i>Your current language is highlighted.</i>",
        "lang_changed": "✅ Language set to <b>{name}</b>.",
    },

    # =========================================================================
    # VIETNAMESE
    # =========================================================================
    "vi": {
        "cmd_start_desc": "Đăng ký nhận tín hiệu + tin tức",
        "cmd_stop_desc": "Hủy đăng ký",
        "cmd_news_desc": "Xem tin mới nhất",
        "cmd_help_desc": "Hướng dẫn sử dụng",
        "cmd_language_desc": "Đổi ngôn ngữ",

        "welcome_title": "✨ <b>Chào mừng đến IS6FX Signals</b> ✨",
        "welcome_intro": "🎉 Bạn đã đăng ký thành công các kênh sau:",
        "welcome_signals": "📈  <b>Tín hiệu giao dịch</b>  — cập nhật theo thời gian thực",
        "welcome_news": "📰  <b>Bản tin tài chính</b>  — mỗi sáng lúc 07:30",
        "welcome_alerts": "🔔  <b>Cảnh báo thị trường</b>  — khi có biến động quan trọng",
        "welcome_tip": "💡 <i>Bấm vào nút bên dưới để bắt đầu.</i>",
        "welcome_stop_hint": "🛑 <i>Dùng /stop bất cứ lúc nào để hủy đăng ký.</i>",
        "welcome_back": "✅ <b>Chào mừng bạn quay lại!</b>\n{thin}\nBạn vẫn đang đăng ký và sẽ tiếp tục nhận tín hiệu.",
        "stopped": "🛑 <b>Đã hủy đăng ký</b>\n{thin}\nBạn sẽ không còn nhận tín hiệu hay tin tức nữa.\n👋 <i>Gửi /start bất cứ lúc nào để quay lại.</i>",

        "help_user_title": "🧭 <b>IS6FX Signals — Trợ giúp</b>",
        "help_user_section": "<b>👤 Lệnh dành cho bạn</b>",
        "help_user_start": "├ 🟢 /start — đăng ký nhận tín hiệu + tin tức",
        "help_user_stop": "├ 🔴 /stop — hủy đăng ký",
        "help_user_news": "├ 📰 /news — xem tin thị trường mới nhất",
        "help_user_lang": "├ 🌐 /language — đổi ngôn ngữ",
        "help_user_help": "└ ❓ /help — hiển thị menu này",
        "help_user_tip": "💬 <i>Mẹo: bấm vào nút bên dưới để truy cập nhanh.</i>",

        "help_admin_title": "🛡️ <b>IS6FX Signals — Bảng điều khiển Admin</b>",
        "help_admin_user_section": "<b>👤 Lệnh người dùng</b>",
        "help_admin_user_start": "├ 🟢 /start — đăng ký",
        "help_admin_user_stop": "├ 🔴 /stop — hủy đăng ký",
        "help_admin_user_news": "├ 📰 /news — tin mới nhất",
        "help_admin_user_lang": "├ 🌐 /language — đổi ngôn ngữ",
        "help_admin_user_help": "└ ❓ /help — menu này",
        "help_admin_broadcast_section": "<b>⚡ Phát tín hiệu</b>",
        "help_admin_signal": "├ 📈 /signal &lt;nội dung&gt; — gửi tín hiệu giao dịch",
        "help_admin_broadcast": "└ 📢 /broadcast &lt;nội dung&gt; — gửi thông báo bất kỳ",
        "help_admin_review_section": "<b>📰 Duyệt tin tức</b>",
        "help_admin_fetchnews": "├ 🔍 /fetchnews — tải tin mới vào hàng đợi",
        "help_admin_pending": "├ 📑 /pending — danh sách tin chờ duyệt",
        "help_admin_preview": "├ 👁️ /preview &lt;id&gt; — xem ảnh + toàn văn",
        "help_admin_edit": "├ ✏️ /edit &lt;id&gt; &lt;nội dung mới&gt; — chỉnh sửa trước khi gửi",
        "help_admin_approve": "├ ✅ /approve &lt;id&gt; — phát lên kênh + người đăng ký",
        "help_admin_discard": "└ 🗑️ /discard &lt;id&gt; — xóa khỏi hàng đợi",
        "help_admin_sched_section": "<b>⏰ Hẹn giờ</b>",
        "help_admin_schedule": "├ 📅 /schedule &lt;khi nào&gt; &lt;nội dung&gt; — đặt lịch phát",
        "help_admin_schedules": "├ 📄 /schedules — danh sách lịch chờ",
        "help_admin_cancel": "└ 🗑️ /cancel &lt;id&gt; — hủy một lịch",
        "help_admin_ops_section": "<b>🔧 Vận hành</b>",
        "help_admin_stats": "├ 📊 /stats — trạng thái hệ thống",
        "help_admin_sendnews": "└ 🔄 /sendnews — gửi bản tin ngay",
        "help_admin_photo_title": "📸 <b>Đính kèm ảnh</b>",
        "help_admin_photo_desc": "<i>Gửi ảnh kèm chú thích bắt đầu bằng /signal, /broadcast hoặc /schedule để gửi kèm hình ảnh.</i>",
        "help_admin_sched_examples": "📝 <b>Ví dụ /schedule</b>",

        "btn_news": "📰 Tin mới nhất",
        "btn_help": "❓ Trợ giúp",
        "btn_status": "🔔 Trạng thái",
        "btn_stop": "🛑 Hủy đăng ký",
        "btn_language": "🌐 Ngôn ngữ",
        "btn_stats": "📊 Thống kê",
        "btn_schedules": "📄 Lịch chờ",
        "btn_fetchnews": "🔍 Tải tin",
        "btn_pending": "📑 Chờ duyệt",
        "btn_approve": "✅ Duyệt & gửi",
        "btn_discard": "🗑️ Bỏ",
        "btn_view_pending": "📑 Xem tin chờ duyệt",
        "btn_cancel_job": "🗑️ Hủy {job_id}",
        "btn_all_schedules": "📄 Tất cả lịch",

        "admin_only": "⛔ Lệnh này chỉ dành cho quản trị viên.",
        "empty_body": "⚠️ Nội dung trống.",
        "action_unavailable": "⛔ Thao tác không khả dụng.",
        "bot_online": "🟢 <b>Bot đang hoạt động</b>\n{thin}\nBạn sẽ tiếp tục nhận tín hiệu và bản tin hằng ngày.",

        "signal_usage": "<b>Cách dùng:</b>\n<code>/signal BTCUSDT LONG entry=65000 sl=64000 tp=67000</code>\n\n<b>Kèm ảnh:</b> gửi ảnh và đặt lệnh /signal trong phần chú thích,\nhoặc trả lời (reply) một ảnh có sẵn bằng <code>/signal &lt;nội dung&gt;</code>.",
        "broadcast_usage": "Cách dùng: /broadcast <nội dung>\nKèm ảnh: gửi ảnh và đặt /broadcast <nội dung> trong chú thích,\nhoặc reply một ảnh có sẵn bằng /broadcast <nội dung>.",
        "signal_sent": "✅ <b>Đã gửi tín hiệu</b>{img}\n{thin}\n📤 Đã gửi: <b>{delivered}</b>\n⚠️ Thất bại: <b>{failed}</b>",
        "broadcast_sent": "✅ <b>Đã phát thông báo</b>{img}\n{thin}\n📤 Đã gửi: <b>{delivered}</b>\n⚠️ Thất bại: <b>{failed}</b>",
        "signal_card_title": "📈 <b>TÍN HIỆU GIAO DỊCH</b>  •  🆕",
        "signal_disclaimer": "⚠️ <i>Đây không phải lời khuyên đầu tư. Giao dịch có rủi ro — bạn tự chịu trách nhiệm.</i>",

        "digest_title": "📰 <b>Bản tin tài chính hôm nay</b>",
        "digest_count": "🗞️ <b>{n}</b> tin nổi bật sáng nay",
        "digest_sources": "🔗 <i>Nguồn: CafeF • VnExpress • Vietstock</i>",
        "news_loading": "🔄 <i>Đang tải tin thị trường mới nhất…</i>",
        "news_empty": "💭 <b>Hiện chưa có tin mới.</b>\n<i>Vui lòng thử lại sau ít phút.</i>",
        "sendnews_triggered": "Đang gửi bản tin hằng ngày…",

        "stats_title": "📊 <b>Bảng điều khiển hệ thống</b>",
        "stats_audience": "<b>👥 Người nhận</b>",
        "stats_subs": "├ 🟢 Người đăng ký: <b>{n}</b>",
        "stats_channel": "└ {dot} Kênh: <code>{ch}</code>",
        "stats_channel_none": "chưa cấu hình",
        "stats_schedule": "<b>⏰ Lịch trình</b>",
        "stats_daily": "├ 📅 Bản tin hằng ngày: <b>{time}</b> ({tz})",
        "stats_pending": "└ 🕒 Lịch chờ: <b>{n}</b>",
        "stats_integrations": "<b>🔌 Tích hợp</b>",
        "stats_webhook": "├ {dot} Webhook: <b>{state}</b>",
        "stats_email": "└ {dot} Cầu email: <b>{state}</b>",
        "stats_state_on": "BẬT",
        "stats_state_off": "TẮT",

        "fetchnews_loading": "🔍 <i>Đang tải tiêu đề tin…</i>",
        "fetchnews_no_headlines": "⚠️ Không lấy được tin. Hãy kiểm tra NEWS_SOURCES trong .env.",
        "fetchnews_progress": "🔍 Tìm thấy <b>{n}</b> tiêu đề.\n📄 <i>Đang trích xuất nội dung + hình ảnh…</i>",
        "fetchnews_summary": "✅ <b>Tải tin xong</b>\n{div}\n├ 📅 Tin mới đã lưu: <b>{saved}</b>\n├ 🔁 Tin trùng đã bỏ: <b>{dup}</b>\n├ ⚠️ Lỗi trích xuất: <b>{fail}</b>\n└ 📑 Tổng tin chờ duyệt: <b>{total}</b>\n\n<i>Dùng /pending để duyệt.</i>",
        "pending_empty": "💭 <b>Chưa có tin nào chờ duyệt.</b>\n<i>Chạy /fetchnews để tải tin mới.</i>",
        "pending_title": "📑 <b>Tin chờ duyệt</b>",
        "pending_count": "📊 <b>{n}</b> tin đang chờ",
        "pending_legend": "👁️ /preview &lt;id&gt; · ✏️ /edit &lt;id&gt; · ✅ /approve &lt;id&gt; · 🗑️ /discard &lt;id&gt;",
        "preview_usage": "Cách dùng: /preview <id>",
        "approve_usage": "Cách dùng: /approve <id>",
        "discard_usage": "Cách dùng: /discard <id>",
        "edit_usage": "<b>Cách dùng:</b> <code>/edit &lt;id&gt; &lt;nội dung mới&gt;</code>\n<i>Thay thế nội dung bài viết. Tiêu đề và hình ảnh được giữ nguyên.</i>",
        "article_invalid_id": "⚠️ ID không hợp lệ: {raw}",
        "article_not_found": "⚠️ Không tìm thấy tin với ID <code>#{id}</code>.",
        "article_already_status": "⚠️ Tin #{id} đã ở trạng thái <b>{status}</b> — không thể chỉnh sửa.",
        "article_already_approved": "⚠️ Tin #{id} đã được duyệt trước đó.",
        "article_already_discarded": "⚠️ Tin #{id} đã bị bỏ.",
        "article_updated": "✏️ <b>Đã cập nhật tin #{id}</b>\n{thin}\nĐộ dài mới: <b>{n}</b> ký tự.\n<i>Dùng /preview {id} để kiểm tra, sau đó /approve {id}.</i>",
        "article_broadcast_done": "✅ <b>Đã phát tin #{id}</b>\n{thin}\n📤 Đã gửi: <b>{delivered}</b>\n⚠️ Thất bại: <b>{failed}</b>\n📑 Còn chờ duyệt: <b>{left}</b>",
        "article_broadcast_short": "✅ <b>Đã phát tin #{id}</b>\n{thin}\n📤 Đã gửi: <b>{delivered}</b>\n⚠️ Thất bại: <b>{failed}</b>",
        "article_discarded": "🗑️ <b>Đã bỏ tin #{id}.</b>\n📑 Còn chờ duyệt: <b>{left}</b>",
        "article_discarded_short": "🗑️ Đã bỏ tin #{id}.",
        "article_gone": "⚠️ Tin <code>#{id}</code> không còn tồn tại.",
        "article_already_short": "⚠️ Tin #{id} đã ở trạng thái <b>{status}</b>.",
        "article_bad_button": "⚠️ Dữ liệu nút không hợp lệ.",
        "article_status_pending": "đang chờ",
        "article_status_approved": "đã duyệt",
        "article_status_discarded": "đã bỏ",
        "article_read_on": "Đọc trên {source}",
        "preview_header": "XEM TRƯỚC",
        "preview_label": "🔎 <b>{header}</b>  ·  ID <code>#{id}</code>",

        "schedule_usage": "<b>Cách dùng:</b>\n<code>/schedule &lt;khi nào&gt; &lt;nội dung&gt;</code>\n\n<b>Ví dụ</b>\n<code>/schedule 30m BTCUSDT LONG entry=65000</code>\n<code>/schedule 17:30 Mở phiên Âu</code>\n<code>/schedule 2026-05-06 09:00 Nhắc tin NFP</code>\n\nThêm <code>signal:</code> ở đầu để định dạng như tín hiệu giao dịch:\n<code>/schedule 1h signal: BTCUSDT LONG entry=65000 sl=64000</code>\n\nĐính kèm ảnh và đặt /schedule trong chú thích để gửi kèm hình.",
        "schedule_no_body": "⚠️ Bạn đã nhập thời gian nhưng thiếu nội dung.",
        "schedule_empty_signal": "⚠️ Thiếu nội dung tín hiệu sau `signal:`.",
        "schedule_created": "⏰ <b>Đã đặt lịch</b>{img}\n{div}\n├ 🆔 ID: <code>{id}</code>\n├ {icon} Loại: <b>{kind}</b>\n├ 📅 Sẽ gửi lúc: <b>{when}</b>\n└ 📝 Xem trước: <i>{preview}</i>",
        "schedules_empty": "Không có lịch phát nào đang chờ.",
        "schedules_title": "⏰ <b>Lịch phát đang chờ</b>",
        "schedules_count": "📊 <b>{n}</b> lịch chờ",
        "schedules_hint": "🗑️ <i>Hủy lịch:</i> <code>/cancel &lt;id&gt;</code>",
        "cancel_usage": "Cách dùng: /cancel <id>   (xem ID bằng /schedules)",
        "cancel_not_found": "⚠️ Không tìm thấy lịch chờ với ID `{id}`.",
        "cancel_done": "🗑️ <b>Đã hủy</b>\n{thin}\nLịch <code>{id}</code> đã được xóa khỏi hàng đợi.",
        "cancel_done_btn": "⚠️ Không tìm thấy lịch <code>{id}</code> (đã chạy hoặc đã hủy).",
        "scheduled_fire_notice": "⏰ Đã gửi {kind} theo lịch <code>{id}</code>{suffix}.\nĐã gửi: {delivered}, thất bại: {failed}",
        "with_image_suffix": " 🖼️ kèm ảnh",
        "kind_signal": "tín hiệu",
        "kind_broadcast": "thông báo",

        "err_empty_time": "Thiếu thời gian. Ví dụ: `30m` hoặc `17:30`.",
        "err_duration_zero": "Khoảng thời gian phải lớn hơn 0.",
        "err_duration_too_long": "Khoảng thời gian quá dài (tối đa 30 ngày).",
        "err_in_past": "Mốc thời gian {when} đã thuộc quá khứ.",
        "err_unknown_time": "Không đọc được thời gian. Ví dụ: `30m`, `2h`, `1d12h`, `17:30`, `2026-05-06 09:00`.",

        "lang_picker_title": "🌐 <b>Chọn ngôn ngữ</b>\n{thin}\n<i>Ngôn ngữ hiện tại được đánh dấu.</i>",
        "lang_changed": "✅ Đã đổi ngôn ngữ sang <b>{name}</b>.",
    },

    # =========================================================================
    # JAPANESE
    # =========================================================================
    "ja": {
        "cmd_start_desc": "シグナル＋ニュースを購読",
        "cmd_stop_desc": "購読解除",
        "cmd_news_desc": "最新ニュースを取得",
        "cmd_help_desc": "ヘルプを表示",
        "cmd_language_desc": "言語を変更",

        "welcome_title": "✨ <b>IS6FX Signals へようこそ</b> ✨",
        "welcome_intro": "🎉 登録が完了しました!以下を購読中です:",
        "welcome_signals": "📈  <b>取引シグナル</b>  — リアルタイム配信",
        "welcome_news": "📰  <b>毎日のマーケットダイジェスト</b>  — 毎朝 07:30",
        "welcome_alerts": "🔔  <b>マーケットアラート</b>  — 重要なタイミングで",
        "welcome_tip": "💡 <i>下のボタンを押して始めましょう。</i>",
        "welcome_stop_hint": "🛑 <i>いつでも /stop で購読解除できます。</i>",
        "welcome_back": "✅ <b>お帰りなさい!</b>\n{thin}\n引き続き購読中で、シグナルを受信できます。",
        "stopped": "🛑 <b>購読解除しました</b>\n{thin}\nシグナルもニュースも今後は届きません。\n👋 <i>いつでも /start で再購読できます。</i>",

        "help_user_title": "🧭 <b>IS6FX Signals — ヘルプ</b>",
        "help_user_section": "<b>👤 ユーザーコマンド</b>",
        "help_user_start": "├ 🟢 /start — シグナル＋ニュースを購読",
        "help_user_stop": "├ 🔴 /stop — 購読解除",
        "help_user_news": "├ 📰 /news — 最新マーケットニュースを取得",
        "help_user_lang": "├ 🌐 /language — 言語を変更",
        "help_user_help": "└ ❓ /help — このメニューを表示",
        "help_user_tip": "💬 <i>ヒント: 下のボタンで素早く操作できます。</i>",

        "help_admin_title": "🛡️ <b>IS6FX Signals — 管理者コンソール</b>",
        "help_admin_user_section": "<b>👤 ユーザーコマンド</b>",
        "help_admin_user_start": "├ 🟢 /start — 購読",
        "help_admin_user_stop": "├ 🔴 /stop — 購読解除",
        "help_admin_user_news": "├ 📰 /news — 最新ニュース",
        "help_admin_user_lang": "├ 🌐 /language — 言語変更",
        "help_admin_user_help": "└ ❓ /help — このメニュー",
        "help_admin_broadcast_section": "<b>⚡ 配信</b>",
        "help_admin_signal": "├ 📈 /signal &lt;本文&gt; — 取引シグナルを送信",
        "help_admin_broadcast": "└ 📢 /broadcast &lt;本文&gt; — 任意のメッセージ送信",
        "help_admin_review_section": "<b>📰 ニュース審査</b>",
        "help_admin_fetchnews": "├ 🔍 /fetchnews — 最新記事をキューへ取得",
        "help_admin_pending": "├ 📑 /pending — 審査待ち一覧",
        "help_admin_preview": "├ 👁️ /preview &lt;id&gt; — 画像と全文を表示",
        "help_admin_edit": "├ ✏️ /edit &lt;id&gt; &lt;新本文&gt; — 配信前に編集",
        "help_admin_approve": "├ ✅ /approve &lt;id&gt; — チャンネル＋購読者へ配信",
        "help_admin_discard": "└ 🗑️ /discard &lt;id&gt; — キューから削除",
        "help_admin_sched_section": "<b>⏰ スケジュール</b>",
        "help_admin_schedule": "├ 📅 /schedule &lt;いつ&gt; &lt;本文&gt; — 予約配信",
        "help_admin_schedules": "├ 📄 /schedules — 予約一覧",
        "help_admin_cancel": "└ 🗑️ /cancel &lt;id&gt; — 予約をキャンセル",
        "help_admin_ops_section": "<b>🔧 運用</b>",
        "help_admin_stats": "├ 📊 /stats — システム状態",
        "help_admin_sendnews": "└ 🔄 /sendnews — 今すぐダイジェスト配信",
        "help_admin_photo_title": "📸 <b>画像添付</b>",
        "help_admin_photo_desc": "<i>画像にキャプションとして /signal、/broadcast、/schedule を付けると画像付きで送信できます。</i>",
        "help_admin_sched_examples": "📝 <b>/schedule の例</b>",

        "btn_news": "📰 最新ニュース",
        "btn_help": "❓ ヘルプ",
        "btn_status": "🔔 ステータス",
        "btn_stop": "🛑 購読解除",
        "btn_language": "🌐 言語",
        "btn_stats": "📊 統計",
        "btn_schedules": "📄 予約",
        "btn_fetchnews": "🔍 ニュース取得",
        "btn_pending": "📑 審査待ち",
        "btn_approve": "✅ 承認",
        "btn_discard": "🗑️ 破棄",
        "btn_view_pending": "📑 審査待ちを見る",
        "btn_cancel_job": "🗑️ {job_id} を取消",
        "btn_all_schedules": "📄 すべての予約",

        "admin_only": "⛔ このコマンドは管理者専用です。",
        "empty_body": "⚠️ 本文が空です。",
        "action_unavailable": "⛔ 操作は利用できません。",
        "bot_online": "🟢 <b>Bot は稼働中です</b>\n{thin}\nシグナルと毎日のダイジェストを受信します。",

        "signal_usage": "<b>使い方:</b>\n<code>/signal BTCUSDT LONG entry=65000 sl=64000 tp=67000</code>\n\n<b>画像付き:</b> 画像にキャプションとして /signal の本文を付けるか、\n既存の画像に <code>/signal &lt;本文&gt;</code> で返信してください。",
        "broadcast_usage": "使い方: /broadcast <本文>\n画像付き: 画像のキャプションに /broadcast <本文> を付けるか、\n画像に /broadcast <本文> で返信してください。",
        "signal_sent": "✅ <b>シグナル送信完了</b>{img}\n{thin}\n📤 配信: <b>{delivered}</b>\n⚠️ 失敗: <b>{failed}</b>",
        "broadcast_sent": "✅ <b>配信完了</b>{img}\n{thin}\n📤 配信: <b>{delivered}</b>\n⚠️ 失敗: <b>{failed}</b>",
        "signal_card_title": "📈 <b>取引シグナル</b>  •  🆕",
        "signal_disclaimer": "⚠️ <i>これは投資助言ではありません。取引は自己責任でお願いします。</i>",

        "digest_title": "📰 <b>本日のマーケットダイジェスト</b>",
        "digest_count": "🗞️ 今朝の主要記事 <b>{n}</b> 件",
        "digest_sources": "🔗 <i>ソース: CafeF • VnExpress • Vietstock</i>",
        "news_loading": "🔄 <i>最新マーケットニュースを取得中…</i>",
        "news_empty": "💭 <b>新しいニュースはまだありません。</b>\n<i>数分後にもう一度お試しください。</i>",
        "sendnews_triggered": "毎日のダイジェストを今すぐ配信します…",

        "stats_title": "📊 <b>システムダッシュボード</b>",
        "stats_audience": "<b>👥 受信者</b>",
        "stats_subs": "├ 🟢 アクティブ購読者: <b>{n}</b>",
        "stats_channel": "└ {dot} チャンネル: <code>{ch}</code>",
        "stats_channel_none": "未設定",
        "stats_schedule": "<b>⏰ スケジュール</b>",
        "stats_daily": "├ 📅 毎日のニュース: <b>{time}</b> ({tz})",
        "stats_pending": "└ 🕒 予約中: <b>{n}</b>",
        "stats_integrations": "<b>🔌 連携</b>",
        "stats_webhook": "├ {dot} Webhook: <b>{state}</b>",
        "stats_email": "└ {dot} メール連携: <b>{state}</b>",
        "stats_state_on": "ON",
        "stats_state_off": "OFF",

        "fetchnews_loading": "🔍 <i>見出しを取得中…</i>",
        "fetchnews_no_headlines": "⚠️ 見出しが取得できませんでした。.env の NEWS_SOURCES を確認してください。",
        "fetchnews_progress": "🔍 <b>{n}</b> 件の見出しが見つかりました。\n📄 <i>本文と画像を抽出中…</i>",
        "fetchnews_summary": "✅ <b>取得完了</b>\n{div}\n├ 📅 新規保存: <b>{saved}</b>\n├ 🔁 重複スキップ: <b>{dup}</b>\n├ ⚠️ 抽出失敗: <b>{fail}</b>\n└ 📑 審査待ち合計: <b>{total}</b>\n\n<i>/pending で審査してください。</i>",
        "pending_empty": "💭 <b>審査待ちの記事はありません。</b>\n<i>/fetchnews で最新を取得してください。</i>",
        "pending_title": "📑 <b>審査待ち記事</b>",
        "pending_count": "📊 審査待ち <b>{n}</b> 件",
        "pending_legend": "👁️ /preview &lt;id&gt; · ✏️ /edit &lt;id&gt; · ✅ /approve &lt;id&gt; · 🗑️ /discard &lt;id&gt;",
        "preview_usage": "使い方: /preview <id>",
        "approve_usage": "使い方: /approve <id>",
        "discard_usage": "使い方: /discard <id>",
        "edit_usage": "<b>使い方:</b> <code>/edit &lt;id&gt; &lt;新本文&gt;</code>\n<i>記事の本文を置き換えます。タイトルと画像は保持されます。</i>",
        "article_invalid_id": "⚠️ 無効な ID: {raw}",
        "article_not_found": "⚠️ ID <code>#{id}</code> の記事が見つかりません。",
        "article_already_status": "⚠️ 記事 #{id} は既に <b>{status}</b> です — 編集できません。",
        "article_already_approved": "⚠️ 記事 #{id} は既に承認済みです。",
        "article_already_discarded": "⚠️ 記事 #{id} は破棄されています。",
        "article_updated": "✏️ <b>記事 #{id} を更新</b>\n{thin}\n新しい長さ: <b>{n}</b> 文字。\n<i>/preview {id} で確認後、/approve {id} を実行してください。</i>",
        "article_broadcast_done": "✅ <b>記事 #{id} を配信</b>\n{thin}\n📤 配信: <b>{delivered}</b>\n⚠️ 失敗: <b>{failed}</b>\n📑 審査待ち残り: <b>{left}</b>",
        "article_broadcast_short": "✅ <b>記事 #{id} を配信</b>\n{thin}\n📤 配信: <b>{delivered}</b>\n⚠️ 失敗: <b>{failed}</b>",
        "article_discarded": "🗑️ <b>記事 #{id} を破棄。</b>\n📑 審査待ち残り: <b>{left}</b>",
        "article_discarded_short": "🗑️ 記事 #{id} を破棄。",
        "article_gone": "⚠️ 記事 <code>#{id}</code> は存在しません。",
        "article_already_short": "⚠️ 記事 #{id} は既に <b>{status}</b> です。",
        "article_bad_button": "⚠️ 不正なボタンデータです。",
        "article_status_pending": "審査待ち",
        "article_status_approved": "承認済み",
        "article_status_discarded": "破棄",
        "article_read_on": "{source} で読む",
        "preview_header": "プレビュー",
        "preview_label": "🔎 <b>{header}</b>  ·  ID <code>#{id}</code>",

        "schedule_usage": "<b>使い方:</b>\n<code>/schedule &lt;いつ&gt; &lt;本文&gt;</code>\n\n<b>例</b>\n<code>/schedule 30m BTCUSDT LONG entry=65000</code>\n<code>/schedule 17:30 欧州セッション開始</code>\n<code>/schedule 2026-05-06 09:00 NFP リマインダー</code>\n\n本文の先頭に <code>signal:</code> を付けると取引シグナルとして整形されます:\n<code>/schedule 1h signal: BTCUSDT LONG entry=65000 sl=64000</code>\n\n画像のキャプションに付けると画像付きで予約できます。",
        "schedule_no_body": "⚠️ 時刻のみで本文がありません。",
        "schedule_empty_signal": "⚠️ `signal:` の後に本文がありません。",
        "schedule_created": "⏰ <b>予約しました</b>{img}\n{div}\n├ 🆔 ID: <code>{id}</code>\n├ {icon} 種類: <b>{kind}</b>\n├ 📅 配信時刻: <b>{when}</b>\n└ 📝 プレビュー: <i>{preview}</i>",
        "schedules_empty": "予約配信はありません。",
        "schedules_title": "⏰ <b>予約配信一覧</b>",
        "schedules_count": "📊 予約待ち <b>{n}</b> 件",
        "schedules_hint": "🗑️ <i>予約取消:</i> <code>/cancel &lt;id&gt;</code>",
        "cancel_usage": "使い方: /cancel <id>   (ID は /schedules で確認)",
        "cancel_not_found": "⚠️ ID `{id}` の予約は見つかりません。",
        "cancel_done": "🗑️ <b>取消完了</b>\n{thin}\n予約 <code>{id}</code> をキューから削除しました。",
        "cancel_done_btn": "⚠️ 予約 <code>{id}</code> は見つかりません(配信済みまたは取消済み)。",
        "scheduled_fire_notice": "⏰ 予約{kind} <code>{id}</code> を送信{suffix}。\n配信: {delivered}、失敗: {failed}",
        "with_image_suffix": " 🖼️ 画像付き",
        "kind_signal": "シグナル",
        "kind_broadcast": "配信",

        "err_empty_time": "時刻が空です。例: `30m` または `17:30`。",
        "err_duration_zero": "期間は 0 より大きい必要があります。",
        "err_duration_too_long": "期間が長すぎます (最大 30 日)。",
        "err_in_past": "時刻 {when} は既に過去です。",
        "err_unknown_time": "時刻を解釈できません。例: `30m`、`2h`、`1d12h`、`17:30`、`2026-05-06 09:00`。",

        "lang_picker_title": "🌐 <b>言語を選択</b>\n{thin}\n<i>現在の言語が強調表示されています。</i>",
        "lang_changed": "✅ 言語を <b>{name}</b> に設定しました。",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Return the translated string for `key` in language `lang`.

    Falls back to English, then to the key itself if missing everywhere.
    Format kwargs are applied via str.format().
    """
    table = TRANSLATIONS.get(lang) or TRANSLATIONS[DEFAULT_LANG]
    text = table.get(key)
    if text is None:
        # Fall back to English
        text = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError) as e:
            # Don't crash the bot for a bad placeholder — return raw text.
            return f"{text}  [i18n format error: {e}]"
    return text
