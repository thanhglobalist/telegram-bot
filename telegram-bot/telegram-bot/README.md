# Telegram Trading Signals + Daily News Bot

A self-hosted Telegram bot that:

- **Broadcasts trading signals** when you (the admin) send `/signal …` — delivered to your channel and every direct subscriber.
- **Sends a daily news digest** at a time you choose (default `07:30` Asia/Ho_Chi_Minh) by pulling from RSS feeds you configure.
- Lets users subscribe with `/start` and unsubscribe with `/stop`.
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

Send `/start` to **@userinfobot** on Telegram. It replies with your numeric user ID — that's `ADMIN_USER_ID`. Only this user can use `/signal`, `/broadcast`, `/stats`, `/sendnews`.

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
| `/help` | Show command list |

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
│   ├── db.py           # SQLite (subscribers + news dedup)
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
