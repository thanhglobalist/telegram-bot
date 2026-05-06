# Windows Server Setup Guide — Telegram Trading Bot

Tested on **Windows Server 2019 / 2022** and **Windows 10/11**. Two paths depending on what you prefer:

- **Path A — WSL2 + Docker** (recommended, closest to Linux build, ~10 min setup)
- **Path B — Native Python + NSSM** (no Docker, runs as a Windows Service)

Pick one. You don't need both.

---

## 0. Before you start — get these ready

| Item | Where to get it |
|---|---|
| **BOT_TOKEN** | Telegram → `@BotFather` → `/newbot` → copy token |
| **ADMIN_USER_ID** | Telegram → `@userinfobot` → send `/start` → copy your numeric ID |
| **CHANNEL_ID** *(optional)* | Add bot as admin to your channel → forward any channel post to `@userinfobot` → copy the `-100…` ID |
| **VPS access** | RDP login as Administrator |

Connect to the VPS with **Remote Desktop Connection** (`mstsc.exe`) using its IP + admin password.

---

# Path A — WSL2 + Docker (recommended)

## A1. Enable WSL2 (one-time, requires reboot)

Open **PowerShell as Administrator** and run:
```powershell
wsl --install -d Ubuntu-22.04
```
Reboot when prompted. After reboot, Ubuntu opens automatically — set a username and password.

## A2. Install Docker Desktop

Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop). During install, leave **"Use WSL2 instead of Hyper-V"** checked. Launch it once so the Docker engine starts.

Verify in PowerShell:
```powershell
docker --version
docker compose version
```

## A3. Upload the bot code

Copy `telegram-bot.zip` to the server (drag-and-drop into the RDP window works, or use `scp` if you enabled OpenSSH).

In PowerShell:
```powershell
cd C:\
Expand-Archive -Path "$env:USERPROFILE\Desktop\telegram-bot.zip" -DestinationPath "C:\"
cd C:\telegram-bot
```

## A4. Create `.env`

```powershell
copy .env.example .env
notepad .env
```

Fill in:
```env
BOT_TOKEN=123456789:AA...your-token-here
ADMIN_USER_ID=123456789
CHANNEL_ID=-1001234567890
DAILY_NEWS_TIME=07:30
TIMEZONE=Asia/Ho_Chi_Minh
WEBHOOK_ENABLED=false
EMAIL_BRIDGE_ENABLED=false
```

Save and close Notepad.

## A5. Start the bot

```powershell
docker compose up -d --build
docker compose logs -f
```

Make sure **Docker Desktop is set to "Start when you log in"** so the bot survives reboots (Settings → General).

## A6. Day-to-day commands (same as Linux)

```powershell
docker compose logs -f         # live logs
docker compose restart         # apply .env changes
docker compose up -d --build   # update after code changes
docker compose down            # stop
```

---

# Path B — Native Python + NSSM (no Docker)

Use this if you don't want Docker overhead. The bot runs as a real Windows Service.

## B1. Install Python 3.12

Download from [python.org/downloads](https://www.python.org/downloads/). During install **check "Add Python to PATH"**.

Verify:
```powershell
python --version    # should print 3.12.x
```

## B2. Place the code & install dependencies

```powershell
cd C:\
Expand-Archive -Path "$env:USERPROFILE\Desktop\telegram-bot.zip" -DestinationPath "C:\"
cd C:\telegram-bot

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## B3. Create `.env` and fix the DB path

```powershell
copy .env.example .env
notepad .env
```

Fill in the same values as Path A, **plus add this line** (Windows can't write to `/data`):
```env
DB_PATH=C:\telegram-bot\data\bot.db
```

Create the data folder:
```powershell
mkdir C:\telegram-bot\data
```

## B4. Test it runs in the foreground

```powershell
python -m app.bot
```

Send `/start` to your bot in Telegram. If it responds, press `Ctrl+C` to stop and continue to step B5.

## B5. Install NSSM and register as a Windows Service

Download NSSM from [nssm.cc/download](https://nssm.cc/download), unzip, and copy `nssm.exe` to `C:\Windows\System32\`.

Register the service (PowerShell as Admin):
```powershell
nssm install TelegramBot "C:\telegram-bot\venv\Scripts\python.exe" "-m app.bot"
nssm set TelegramBot AppDirectory "C:\telegram-bot"
nssm set TelegramBot AppStdout "C:\telegram-bot\data\bot.log"
nssm set TelegramBot AppStderr "C:\telegram-bot\data\bot.log"
nssm set TelegramBot Start SERVICE_AUTO_START
nssm start TelegramBot
```

Verify:
```powershell
sc query TelegramBot
Get-Content C:\telegram-bot\data\bot.log -Tail 30 -Wait
```

## B6. Day-to-day commands

```powershell
nssm restart TelegramBot              # apply .env changes
nssm stop TelegramBot                 # stop
nssm start TelegramBot                # start
nssm remove TelegramBot confirm       # uninstall service
Get-Content C:\telegram-bot\data\bot.log -Tail 50 -Wait   # tail logs
```

To update code: stop the service → replace files → `pip install -r requirements.txt` → start the service.

---

## Test in Telegram (both paths)

1. Open your bot → press **Start**
2. `/help` → command list appears
3. `/signal BUY EURUSD @ 1.0850 SL 1.0820 TP 1.0900` → broadcasts
4. `/news` → pulls latest headlines
5. `/stats` → shows subscriber count

---

## (Later) Webhook & email bridge on Windows

Edit `.env` and set `WEBHOOK_ENABLED=true` / `EMAIL_BRIDGE_ENABLED=true` with the same values shown in the Linux guide. Then:

- **Path A**: `docker compose up -d --build`
- **Path B**: `nssm restart TelegramBot`

Open port 8080 in Windows Firewall (PowerShell as Admin):
```powershell
New-NetFirewallRule -DisplayName "TelegramBot Webhook" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

TradingView alert URL: `http://YOUR_VPS_IP:8080/tv-webhook/YOUR_WEBHOOK_SECRET`

---

## Security checklist

- [ ] Rotate the Administrator password after setup
- [ ] Restrict RDP to your IP via Windows Firewall (or use a VPN)
- [ ] Only open port 8080 if webhook is enabled
- [ ] Never commit `.env` to Git
- [ ] Enable Windows Update auto-install for security patches
