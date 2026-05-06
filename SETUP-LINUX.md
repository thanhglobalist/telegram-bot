# Linux VPS Setup Guide — Telegram Trading Bot

Tested on **Ubuntu 22.04 / 24.04** (Debian 12 works the same). Works on any cloud VPS (Hetzner, DigitalOcean, Vultr, AWS, Contabo).

You will end up with:
- Bot running 24/7 as a Docker container (auto-restart on reboot)
- SQLite database persisted in `./data`
- Logs viewable any time with one command

---

## 0. Before you start — get these ready

| Item | Where to get it |
|---|---|
| **BOT_TOKEN** | Telegram → `@BotFather` → `/newbot` → copy token |
| **ADMIN_USER_ID** | Telegram → `@userinfobot` → send `/start` → copy your numeric ID |
| **CHANNEL_ID** *(optional)* | Add bot as admin to your channel → forward any channel post to `@userinfobot` → copy the `-100…` ID |
| **VPS access** | SSH login as `root` or a sudo user |

---

## 1. Connect to the VPS

From your laptop:
```bash
ssh root@YOUR_VPS_IP
```

---

## 2. Install Docker (one-time, ~2 minutes)

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version    # sanity check
```

---

## 3. Upload the bot code

**Option A — from your laptop** (recommended):
```bash
scp telegram-bot.zip root@YOUR_VPS_IP:/opt/
```

Then on the VPS:
```bash
cd /opt
apt install -y unzip
unzip telegram-bot.zip
cd telegram-bot
```

**Option B — clone from your own Git repo** if you've pushed it:
```bash
cd /opt
git clone YOUR_REPO_URL telegram-bot
cd telegram-bot
```

---

## 4. Create the `.env` config file

```bash
cp .env.example .env
nano .env
```

Fill in at minimum:
```env
BOT_TOKEN=123456789:AA...your-token-here
ADMIN_USER_ID=123456789
CHANNEL_ID=-1001234567890        # leave blank if no channel
DAILY_NEWS_TIME=07:30
TIMEZONE=Asia/Ho_Chi_Minh

# Leave these OFF for now:
WEBHOOK_ENABLED=false
EMAIL_BRIDGE_ENABLED=false
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

## 5. Start the bot

```bash
docker compose up -d --build
```

Check it's alive:
```bash
docker compose logs -f
```
You should see `Application started` and the scheduler kicking in. Press `Ctrl+C` to stop tailing logs (the bot keeps running).

---

## 6. Test in Telegram

1. Open your bot in Telegram → press **Start**
2. Send `/help` — you'll get the command list
3. Send `/signal BUY EURUSD @ 1.0850 SL 1.0820 TP 1.0900` — it should broadcast
4. Send `/news` — pulls the latest headlines
5. Send `/stats` — shows subscriber count

---

## 7. Useful day-to-day commands

```bash
# View live logs
docker compose logs -f

# Restart after editing .env
docker compose restart

# Update code (after re-uploading zip / git pull)
docker compose up -d --build

# Stop the bot
docker compose down

# Check status
docker compose ps
```

The container has `restart: unless-stopped` set, so it survives VPS reboots automatically.

---

## 8. (Later) Enable webhook or email bridge

When you want TradingView signals to flow in automatically, edit `.env`:

```env
# Paid TradingView plan → webhook
WEBHOOK_ENABLED=true
WEBHOOK_SECRET=pick-a-long-random-string
WEBHOOK_PORT=8080

# Free TradingView plan → email bridge (Gmail)
EMAIL_BRIDGE_ENABLED=true
IMAP_HOST=imap.gmail.com
IMAP_USER=your-gmail@gmail.com
IMAP_PASS=your-16-char-app-password   # from Google Account → App Passwords
```

Then `docker compose up -d --build`. If using webhook, open port 8080 in your firewall:
```bash
ufw allow 8080/tcp
```

TradingView alert URL: `http://YOUR_VPS_IP:8080/tv-webhook/YOUR_WEBHOOK_SECRET`

---

## 9. Security checklist

- [ ] Rotate the root/admin password after setup
- [ ] `ufw enable` with only ports 22 and 8080 (if webhook) open
- [ ] Disable root SSH login, use a sudo user + SSH key
- [ ] Never commit `.env` to Git
