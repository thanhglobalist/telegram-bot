# Telegram Trading Signals + Daily News Bot

**Current version: `v3.0.1`** · [Changelog](#changelog) · IS6FX Vietnam

A self-hosted Telegram bot that:

- **Broadcasts trading signals** when you (the admin) send `/signal …` — delivered to your channel and every direct subscriber. Photos can be attached.
- **Curates news** from RSS feeds: pull articles with `/fetchnews`, review them with `/pending` + `/preview`, then `/approve` to broadcast (image + full body).
- **Schedules future broadcasts** with `/schedule` (relative or absolute times).
- **Sends a daily news headline digest** at a time you choose (default `07:30` Asia/Ho_Chi_Minh).
- Lets users subscribe with `/start` and unsubscribe with `/stop`.
- Inline keyboard buttons for one-tap actions — no need to memorize commands.
- Runs as a single Python process. No public ports needed (uses long polling).

---

## 1. Get a bot token from @BotFather

1. Open Telegram, search for **@BotFather**, start a chat.
2. Send `/newbot`.
3. Enter a display name (e.g. `My Trading Bot`).
4. Enter a username — must end in `bot` (e.g. `mytradingsignals_bot`).
5. BotFather replies with a token like `123456789:AAExample…`. **Copy it** — that's `BOT_TOKEN`.
6. (Recommended) Send `/setprivacy` → choose your bot → **Disable**. This lets the bot read commands sent in groups too.
7. (Optional) Send `/setdescription`, `/setabouttext`, `/setuserpic` to brand it.

## 2. Find your admin user ID

Send `/start` to **@userinfobot** on Telegram. It replies with your numeric user ID — that's `ADMIN_USER_ID`. Only this user can use admin commands like `/signal`, `/broadcast`, `/schedule`, `/fetchnews`, `/approve`, `/stats`.

## 3. (Optional) Create a channel

If you want signals + news posted to a public channel:

1. In Telegram → **New Channel** → make it **Public** and pick a username (e.g. `mysignalshub`).
2. Open the channel → **Administrators** → **Add Administrator** → search for your bot's username → grant **Post Messages** permission.
3. In `.env`, set `CHANNEL_ID=@mysignalshub` (with the `@`).

If you skip this, the bot only sends to direct subscribers — leave `CHANNEL_ID` empty.

## 4. Configure the bot

```bash
cp .env.example .env
nano .env
```

Fill in `BOT_TOKEN`, `ADMIN_USER_ID`, optional `CHANNEL_ID`. Adjust `DAILY_NEWS_TIME` and `NEWS_SOURCES` to taste.

> **News source note.** ForexFactory's RSS feed blocks most automated requests, so the defaults use Investing.com, ForexLive, and FinanceMagnates — all reliable. You can paste any RSS URL into `NEWS_SOURCES` (comma-separated). Plain HTML pages also work but are less stable.

---

## 5a. Deploy with Docker (recommended)

Requires Docker + Docker Compose on your VPS.

```bash
# On your VPS
git clone <this-repo> /opt/telegram-bot   # or scp the folder
cd /opt/telegram-bot
cp .env.example .env && nano .env         # fill in tokens

docker compose up -d --build              # start
docker compose logs -f                    # watch logs
docker compose restart                    # after editing .env
docker compose down                       # stop
```

Subscriber data is persisted in `./data/bot.db` on the host.

## 5b. Deploy with systemd (no Docker)

Requires Python 3.11+ on the VPS.

```bash
# On your VPS, as root or with sudo
sudo useradd -r -m -d /opt/telegram-bot botuser
sudo mkdir -p /opt/telegram-bot && sudo chown botuser:botuser /opt/telegram-bot
sudo -u botuser bash <<'EOF'
cd /opt/telegram-bot
# Copy your local repo files here (git clone, scp, rsync, etc.)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
EOF

sudo nano /opt/telegram-bot/.env          # fill in tokens
# Inside .env, set: DB_PATH=/opt/telegram-bot/data/bot.db
sudo -u botuser mkdir -p /opt/telegram-bot/data

# Install + start service
sudo cp deploy/trading-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot
sudo systemctl status trading-bot
sudo journalctl -u trading-bot -f         # follow logs
```

To upgrade, replace the source files and run `sudo systemctl restart trading-bot`.

---

## 6. Use the bot

Open Telegram, search for your bot's username, send `/start`. You should see the welcome message.

### Public commands

| Command | Description |
|---|---|
| `/start` | Subscribe to signals + daily news |
| `/stop` | Unsubscribe |
| `/news` | Get latest news on demand |
| `/language` | Switch UI language (English / Tiếng Việt / 日本語) |
| `/help` | Show command list |

### Languages

The bot ships with three languages: **English**, **Tiếng Việt** (default), and **日本語**. On first `/start`, the bot auto-detects the user's Telegram client language; users can override anytime with `/language`. Each user's choice is stored per-account in the database.

Trading signals and admin broadcasts: the **wrapper** (header, disclaimer, footer) is translated per recipient; the admin-typed body is sent as-is. News article bodies stay in the source language; only the surrounding labels translate. Channel posts use the bot's `DEFAULT_LANG` (Vietnamese).

To add a new language, edit `app/i18n.py`: add the code to `LANGUAGES`, add a `{key: text}` dict to `TRANSLATIONS`, and optionally extend `LANG_CODE_MAP` for auto-detection.

### Admin-only commands (only your `ADMIN_USER_ID`)

| Command | Description |
|---|---|
| `/signal <text>` | Broadcast a formatted trading signal to channel + all subscribers |
| `/broadcast <text>` | Broadcast a plain message |
| `/stats` | Show subscriber count + config |
| `/sendnews` | Trigger the daily news digest immediately |

### Signal examples

```
/signal BTCUSDT LONG
Entry: 65,400
SL: 64,200
TP1: 66,800   TP2: 68,500
Risk: 1%
```

```
/signal <b>EURUSD SHORT</b>
Entry: 1.0820
SL: 1.0865
TP: 1.0750
```

The text is sent verbatim with HTML formatting allowed (`<b>`, `<i>`, `<code>`, `<a href="…">`, etc.). The bot wraps it with a header and disclaimer.

---

## 7. Troubleshooting

- **Bot doesn't respond.** Check `docker compose logs` / `journalctl -u trading-bot`. Most issues are wrong `BOT_TOKEN` or wrong `ADMIN_USER_ID`.
- **`/signal` says "admin only".** Your `ADMIN_USER_ID` doesn't match the user sending the command. Re-check with @userinfobot.
- **Channel posts fail.** Make sure the bot is an **Administrator** in the channel with **Post Messages** permission, and `CHANNEL_ID` starts with `@`.
- **No news coming in.** Run `/news` to test. If it returns nothing, the feed URL may be down/blocked — try replacing it in `.env` with one from the suggested list.
- **Lots of "Forbidden" failures during broadcast.** Normal — those users blocked the bot. They're auto-removed from the active list.
- **Want webhooks instead of polling?** The bot uses long polling (no inbound port needed). For higher throughput, switch the `run_polling()` call in `app/bot.py` to `run_webhook()`. See the [Telegram docs](https://core.telegram.org/bots/api#setwebhook).

---

## 8. File map

```
telegram-bot/
├── app/
│   ├── bot.py          # commands, scheduler, broadcast
│   ├── config.py       # env var loader
│   ├── db.py           # SQLite (subscribers + news dedup + per-user language)
│   ├── i18n.py         # translation tables (EN / VI / JA)
│   ├── scheduler.py    # /schedule time parser
│   └── news.py         # RSS + HTML news fetcher
├── deploy/
│   └── trading-bot.service   # systemd unit
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example        # copy to .env and fill in
└── README.md
```

---

## 9. Auto signals from TradingView

The bot ships with **two ways** to receive automated TradingView signals. Pick the one that matches your TradingView plan. Both are off by default — flip them on in `.env`.

### Option A — Webhook (TradingView Essential plan or higher, ~$15/mo)

Near-instant (<1 second). Requires the bot to be reachable from the public internet on HTTPS.

**Step 1.** Generate a secret and enable in `.env`:

```
WEBHOOK_ENABLED=true
WEBHOOK_PORT=8080
WEBHOOK_SECRET=<paste output of: python -c 'import secrets; print(secrets.token_urlsafe(32))'>
```

**Step 2.** Put HTTPS in front of port 8080. Easiest path is Caddy on the same VPS:

```caddy
trading.yourdomain.com {
    reverse_proxy localhost:8080
}
```

**Step 3.** Restart the bot, then in TradingView's alert dialog:
- *Notifications* tab → check **Webhook URL** → paste:
  `https://trading.yourdomain.com/tv-webhook/<WEBHOOK_SECRET>`
- *Settings* tab → *Message* → paste a JSON payload like:

```json
{
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "sl": "{{plot_0}}",
  "tp": "{{plot_1}}",
  "note": "RSI cross"
}
```

The bot accepts JSON or plain text — if you don't use JSON, the whole message is forwarded.

**Quick local test:**
```bash
curl -X POST https://trading.yourdomain.com/tv-webhook/<SECRET> \
  -H 'Content-Type: application/json' \
  -d '{"action":"BUY","symbol":"BTCUSDT","price":65000,"sl":64000,"tp":67000}'
```

You should see the formatted signal arrive in your channel and DMs within a second.

### Option B — Email bridge (works with TradingView free plan)

5–30 second latency, zero TradingView cost. The bot polls a Gmail mailbox and forwards every TradingView alert email.

**Step 1.** Set up a dedicated Gmail account (or use an existing one). Then:
- Enable **2-Step Verification** ([myaccount.google.com](https://myaccount.google.com/security))
- Create an **App Password** (Security → App passwords) — 16 characters, no spaces

**Step 2.** Enable in `.env`:

```
EMAIL_BRIDGE_ENABLED=true
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=you@gmail.com
IMAP_PASSWORD=<the 16-char App Password>
IMAP_SENDER_FILTER=noreply@tradingview.com
IMAP_POLL_SECONDS=20
```

**Step 3.** Restart the bot, then in TradingView's alert dialog:
- *Notifications* tab → check **Send email**
- (TradingView sends to the email on your TradingView account — if that's not the same as `IMAP_USER`, use **Send email-to-SMS** with the IMAP address instead.)
- *Message* field — same JSON format as Option A, or free-form text.

**How it works:** every `IMAP_POLL_SECONDS`, the bot connects, fetches unread messages from `IMAP_SENDER_FILTER`, parses them, broadcasts, and marks them seen. Other emails in the inbox are left alone.

### Which one should I use?

| | Webhook | Email bridge |
|---|---|---|
| TradingView plan needed | Essential ($14.95/mo) or higher | Free works |
| Latency | < 1 second | 5–30 seconds |
| Reachable from internet? | Required (HTTPS) | Not needed |
| Best for | Scalping, time-sensitive entries | Swing trading, signal channels |

You can enable **both** simultaneously — the bot dedupes nothing, so set this up only if you genuinely want each event sent twice.

---

## 10. Extending further

- **Per-user signal tiers.** Add a `tier` column to the `subscribers` table and filter the broadcast loop.
- **Hourly news instead of daily.** Change `run_daily` to `run_repeating(interval=3600)` in `bot.py`.
- **More external sources.** Anything that can POST HTTP — 3Commas, custom scripts, Zapier — can hit the webhook endpoint with a JSON payload.

---

## Changelog

All notable changes to this bot are listed here. Versions follow [Semantic Versioning](https://semver.org/) — MAJOR for breaking changes, MINOR for new features, PATCH for fixes.

### v3.0.1 — 2026-05-06
**Fix — news sources fallback**

User reported the daily digest still pulled English headlines (Investinglive, Finance Magnates, Forex News) even after upgrading to v2.1.0+. Root cause: the VPS `.env` carried the old English `NEWS_SOURCES=...` from v1.x and was never updated; the bot was loading those URLs verbatim with no safety net.

- `Config.from_env()` now hardcodes the three Vietnamese RSS feeds (CafeF, VnExpress, Vietstock) as a fallback. Used whenever `NEWS_SOURCES` is missing or empty in `.env`. An out-of-date `.env` can no longer silently downgrade the bot to English sources — to override, set `NEWS_SOURCES=` explicitly.
- New admin command **`/sources`** — prints the active feed list so you can verify what the bot is actually pulling without SSHing into the VPS.
- Startup now logs the active news sources at `INFO` level: `News sources (3): https://cafef.vn/…, https://vnexpress.net/…, https://vietstock.vn/…`.

### v3.0.0 — 2026-05-06
**Multi-language support — English, Tiếng Việt, 日本語**

MAJOR: schema and architecture change — every user now has a per-account language preference and all UI strings flow through a central translation table.

- New `app/i18n.py` module with three full translation tables (EN / VI / JA) covering ~146 keys: welcome, help (user + admin), buttons, signal/broadcast wrappers, news digest, stats dashboard, news review queue, scheduler errors, and the language picker itself.
- New `/language` command with an inline keyboard listing all supported languages. The current language is marked with ✓.
- Per-user language stored in the `subscribers.language` column. Existing v2.x databases are migrated automatically with a default of `vi` (no manual steps).
- `LANG_CODE_MAP` + `i18n.normalize()` auto-detect language from Telegram's `language_code` on first `/start` (e.g. `en-US` → `en`, `ja-JP` → `ja`). Unknown codes fall back to `DEFAULT_LANG = vi`.
- `set_my_commands(…, language_code=…)` now registered for every supported language so Telegram's “/” menu shows native command descriptions per client locale.
- Trading signals: admin-typed body unchanged; only the wrapper (“TRADING SIGNAL” header, disclaimer, footer) translates per recipient.
- Daily news digest: each subscriber receives the digest with their preferred wrapper language (article bodies stay in source language).
- Channel posts use `DEFAULT_LANG` (one channel = one language).
- Scheduler errors refactored: `TimerError` now carries an i18n key + format vars; the caller in `bot.py` translates per user.
- **Bug fix:** `parse_when()` no longer accidentally swallows its own `TimerError("err_in_past")` because of `TimerError extends ValueError` — the `try/except ValueError` was rewritten to wrap only the `strptime` call.
- Adding a fourth language is now a 3-step change: add the code to `LANGUAGES`, add a translation dict to `TRANSLATIONS`, optionally extend `LANG_CODE_MAP`. No bot code touches strings directly.

### v2.2.0 — 2026-05-06
**Localization — tiếng Việt toàn bộ giao diện**
- All user-facing text translated to Vietnamese: `/start`, `/help`, `/stats`, `/signal`, `/broadcast`, `/news`, `/fetchnews`, `/pending`, `/preview`, `/edit`, `/approve`, `/discard`, `/schedule`, `/schedules`, `/cancel`, `/sendnews`.
- All inline keyboard buttons translated (“Tin mới nhất”, “Trợ giúp”, “Trạng thái”, “Hủy đăng ký”, “Thống kê”, “Lịch chờ”, “Tải tin”, “Chờ duyệt”, “Duyệt & gửi”, “Bỏ”).
- All error & confirmation messages translated (admin-only, invalid id, empty body, schedule errors).
- `/stats` redesigned as “Bảng điều khiển hệ thống” with Vietnamese section labels.
- Trading signal card now reads “TÍN HIỆU GIAO DỊCH” with Vietnamese disclaimer.
- Bot command descriptions registered with Telegram are now Vietnamese (visible in the / menu).
- Scheduler error messages localized in `app/scheduler.py`.
- **Bug fix:** added missing `import uuid` in `app/bot.py` (caused `/schedule` to crash with `NameError`).

### v2.1.0 — 2026-05-06
**Vietnamese news sources**
- Replaced English feeds with **CafeF**, **VnExpress Kinh doanh**, and **Vietstock**.
- New default `NEWS_SOURCES` in `.env.example` points to the 3 Vietnamese RSS endpoints.
- Daily digest header switched to Vietnamese: “Bản tin tài chính hôm nay” / “Nguồn: CafeF • VnExpress • Vietstock”.
- `Accept-Language` header in `app/news.py` now leads with `vi` so VnExpress stops returning 406.
- Article scraper unchanged — `og:image` + UTF-8 already work for VN diacritics.

### v2.0.0 — 2026-05-06
**News review queue (breaking change to news flow)**
- New `/fetchnews` — pulls articles, scrapes main image (`og:image`) + full body, stores in DB for review.
- New `/pending` — list articles awaiting review.
- New `/preview <id>` — see image + full text with **Approve** / **Discard** inline buttons.
- New `/edit <id> <text>` — modify body before broadcasting.
- New `/approve <id>` — broadcast image + full text to channel + subscribers.
- New `/discard <id>` — remove from queue.
- New SQLite table `pending_articles` (auto-pruned after 14 days).
- Browser-style User-Agent in `app/news.py` so anti-bot sources (Investing.com) don't return 403.
- **Breaking:** the daily 07:30 digest is now optional — admins curate which articles ship via `/approve`.

### v1.5.0 — 2026-05-05
**UI redesign — System Dashboard & inline keyboards**
- Inline keyboard buttons on `/start`, `/help`, `/stats` for one-tap navigation.
- Icons throughout, tree connectors (`├` `└`), status pills (🟢 / ⚪️).
- Redesigned `/stats` as a "System Dashboard" with sections for subscribers, news, scheduler, and uptime.
- Brand footer "IS6FX Vietnam" appended to all signals & digests via `_format_signal()`.

### v1.4.0 — 2026-05-05
**Scheduled broadcasts**
- `/schedule <when> <text>` — supports relative (`30m`, `1h30m`) and absolute (`17:30`, `2026-05-06 09:00`) times.
- `/schedules` — list pending jobs.
- `/cancel <id>` — cancel a job before it fires.
- New module `app/scheduler.py` with `parse_when()`, `split_when_and_body()`, `ScheduledJob`, `TimerError`.
- Built on python-telegram-bot's JobQueue (in-memory; restart clears pending jobs).

### v1.3.0 — 2026-05-05
**Image attachments**
- `/signal` and `/broadcast` now accept photos via caption **or** reply-to-photo.
- Caption-limit handling: photo sent first, text follow-up if body > 1024 chars.
- Throttling tuned for media: 25 msg/sec text, 20 photo (file_id), 18 photo (URL).
- New helpers `_send_one`, `_extract_photo_id`, `_broadcast_with_photo_url`.

### v1.2.0 — 2026-05-04
**Deployment guides + DevOps JD**
- `SETUP-LINUX.md` — Ubuntu + Docker single-path guide.
- `SETUP-WINDOWS.md` — Path A (WSL2 + Docker), Path B (Native Python + NSSM service).
- `JD-DevOps.md` — remote, Vietnam-based DevOps role description.

### v1.1.0 — 2026-05-04
**External signal sources (opt-in)**
- FastAPI webhook receiver on port `8080` (`POST /tv-webhook/{secret}`) for TradingView **paid** plans.
- IMAP email bridge (Gmail) polling every 20s for TradingView **free** plans.
- Both feature-flagged via `.env` (`WEBHOOK_*`, `IMAP_*`) — disabled by default.
- Architecture mindmap published.

### v1.0.0 — 2026-05-04
**Initial release**
- Commands: `/start`, `/stop`, `/signal`, `/broadcast`, `/news`, `/help`, `/stats`, `/sendnews`.
- Daily news digest at **07:30 Asia/Ho_Chi_Minh**.
- Sources: Investing.com, ForexLive, FinanceMagnates RSS.
- SQLite tables: `subscribers`, `seen_news`.
- Docker + systemd deployment paths.

---

*Maintained by IS6FX Vietnam. To bump the version after a change, ask Computer to update this Changelog — it will edit this section going forward.*
