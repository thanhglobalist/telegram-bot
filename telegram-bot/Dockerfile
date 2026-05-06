FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (tzdata for ZoneInfo, ca-certificates for HTTPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# SQLite + state lives here. Mount a volume to persist subscribers across restarts.
RUN mkdir -p /data
VOLUME ["/data"]

# Webhook receiver port (only used when WEBHOOK_ENABLED=true)
EXPOSE 8080

# Non-root user
RUN useradd -r -u 1001 -g root botuser && chown -R botuser:root /data
USER botuser

CMD ["python", "-m", "app.bot"]
