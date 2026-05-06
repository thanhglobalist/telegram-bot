# Job Description — DevOps Engineer (Telegram Trading Bot)

**Company:** IS6FX Vietnam
**Location:** 100% Remote (Vietnam-based candidates only)
**Engagement:** Full-time / Part-time / Contract (open to discussion)
**Reporting to:** Business Owner / Tech Lead

---

## About the project

IS6FX Vietnam is launching a Telegram-based trading signals and financial news service. The system is a Python bot (python-telegram-bot v21) that:

- Broadcasts manual `/signal` commands to a Telegram channel and direct subscribers
- Pushes a daily news digest from Investing.com, ForexLive, and FinanceMagnates RSS feeds at 07:30 (Asia/Ho_Chi_Minh)
- Optionally receives TradingView alerts via webhook (FastAPI on port 8080) or email bridge (IMAP polling Gmail)
- Persists subscribers and news dedup state in SQLite

The codebase is already built, Dockerized, and documented. We need a DevOps engineer to **deploy, harden, and maintain** it on our VPS, then keep it running reliably as we scale.

---

## What you'll do

### Initial setup (week 1–2)
- Deploy the bot on our VPS (Linux preferred; Windows Server with WSL2 acceptable) following the existing `SETUP-LINUX.md` / `SETUP-WINDOWS.md` runbooks
- Configure `.env` with production secrets (BOT_TOKEN, ADMIN_USER_ID, CHANNEL_ID, IMAP credentials)
- Set up Docker + Docker Compose, enable auto-restart on reboot
- Configure firewall (UFW or Windows Firewall), open only required ports (22, 8080)
- Rotate root password, disable password SSH login, set up SSH key auth
- Verify all bot commands work end-to-end in Telegram (`/start`, `/help`, `/signal`, `/news`, `/stats`, `/broadcast`)

### Ongoing operations
- Monitor bot uptime, container health, and Telegram API rate-limit errors
- Set up log aggregation and alerting (Telegram alert to admin / email / Grafana — your call)
- Manage SQLite backups (daily snapshot of `./data/bot.db` to off-server storage)
- Apply OS security patches monthly
- Rotate webhook secrets and IMAP app passwords on schedule
- Deploy new code versions via `docker compose up -d --build` with zero-downtime where possible
- Maintain DNS / TLS if we add a domain for the webhook (Caddy or nginx + Let's Encrypt)

### Scaling & reliability
- Migrate from SQLite to PostgreSQL when subscriber count exceeds ~5,000
- Add a second VPS for failover or load distribution if needed
- Set up CI/CD pipeline (GitHub Actions → registry → VPS pull) so the developer can ship without you touching the server
- Performance-tune broadcast throughput (currently throttled to 25 msg/sec under Telegram's 30/sec limit)

---

## Required skills

- **Linux administration** — Ubuntu/Debian, systemd, UFW, SSH hardening, cron
- **Docker + Docker Compose** — building images, volumes, networks, log drivers, `restart: unless-stopped`
- **Python runtime knowledge** — virtualenv, pip, debugging a Python 3.12 app (you don't need to write features, but you should read tracebacks)
- **Networking** — TCP/UDP basics, port forwarding, reverse proxies (nginx or Caddy), TLS certificates
- **Git** — clone, pull, branch, basic merge conflict resolution
- **Shell scripting** — Bash for cron jobs, backups, health checks
- **Secrets management** — `.env` discipline, never commit secrets, rotate on schedule

## Nice-to-have

- Windows Server administration (PowerShell, NSSM, Windows Firewall) — we have a Windows VPS option
- WSL2 setup experience
- Telegram Bot API familiarity (rate limits, webhook vs long-polling trade-offs)
- FastAPI / uvicorn deployment patterns
- IMAP / email infrastructure (Gmail App Passwords, OAuth2 if we move off basic auth)
- Monitoring stack — Prometheus, Grafana, Loki, or a SaaS like UptimeRobot / Better Stack
- CI/CD — GitHub Actions, GitLab CI
- Cloudflare (DNS, tunnels, WAF) for hiding the VPS origin
- Trading / fintech domain interest — you'll be on call when markets move

---

## Deliverables in your first 30 days

1. Bot deployed and running 24/7 with > 99% uptime
2. Daily SQLite backup automated and verified (test restore once)
3. Monitoring dashboard or alert channel set up — admin gets notified within 5 minutes of an outage
4. Runbook updated with any environment-specific notes (paths, credentials location, contact tree)
5. Documented rollback procedure for failed deploys

---

## Working conditions

- **Fully remote** — work from anywhere in Vietnam
- **Time zone:** Asia/Ho_Chi_Minh (+07). Most maintenance windows during ASEAN off-hours
- **On-call:** Light. Bot supports trading users — outages during London/NY market sessions are higher priority
- **Communication:** Telegram for real-time, email for formal, GitHub/GitLab for code
- **Tools we already use:** Telegram, Docker, GitHub, Google Workspace (Drive, Calendar, Meet)
- **Equipment:** Bring your own laptop. We provide VPS access and any paid SaaS accounts needed
- **Meetings:** Async-first. Weekly 30-min sync via Google Meet, otherwise Telegram

---

## How to apply

Send the following to **thanhng39@gmail.com** with subject `DevOps — [Your Name]`:

1. CV / LinkedIn
2. Brief note (max 200 words): describe a production outage you handled — what broke, how you found it, how you fixed it
3. GitHub or portfolio link if you have one
4. Your availability and expected rate

We'll reply within 5 business days. Shortlisted candidates will get a 30-min screening call followed by a small paid trial task (deploy a sample container on a test VPS, ~2 hours).

---

*IS6FX Vietnam is an equal-opportunity environment. We hire based on skill, reliability, and cultural fit.*
