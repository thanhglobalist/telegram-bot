"""Daily news fetcher. Supports RSS feeds and falls back to plain HTML scraping."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; TelegramNewsBot/1.0)"
TIMEOUT = httpx.Timeout(15.0)


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: datetime | None
    guid: str  # stable id for dedup

    def render(self) -> str:
        """Telegram HTML-safe one-line render."""
        title = _escape_html(self.title)
        src = _escape_html(self.source)
        return f'• <a href="{_escape_html(self.link)}">{title}</a>  <i>— {src}</i>'


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _looks_like_rss(url: str) -> bool:
    u = url.lower()
    return any(tok in u for tok in ("rss", "feed", ".xml", "atom"))


def fetch_news(sources: tuple[str, ...], limit_per_source: int = 10) -> list[NewsItem]:
    items: list[NewsItem] = []
    for url in sources:
        try:
            if _looks_like_rss(url):
                items.extend(_fetch_rss(url, limit_per_source))
            else:
                items.extend(_fetch_html(url, limit_per_source))
        except Exception as e:
            log.warning("Failed to fetch %s: %s", url, e)
    # Sort newest first; items without timestamp go to the bottom.
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


def _fetch_rss(url: str, limit: int) -> list[NewsItem]:
    parsed = feedparser.parse(url, agent=USER_AGENT)
    source = parsed.feed.get("title") or url
    out: list[NewsItem] = []
    for entry in parsed.entries[:limit]:
        published: datetime | None = None
        if getattr(entry, "published_parsed", None):
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = None
        guid = entry.get("id") or entry.get("link") or entry.get("title", "")
        if not guid:
            continue
        out.append(
            NewsItem(
                title=entry.get("title", "(no title)").strip(),
                link=entry.get("link", url),
                source=source,
                published=published,
                guid=guid,
            )
        )
    return out


def _fetch_html(url: str, limit: int) -> list[NewsItem]:
    """Very generic fallback: pulls the first N <article>/<h2>/<h3> headlines."""
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    source = (soup.title.string.strip() if soup.title and soup.title.string else url)

    seen_titles: set[str] = set()
    out: list[NewsItem] = []
    candidates = soup.select("article a, h2 a, h3 a")
    for a in candidates:
        title = a.get_text(strip=True)
        link = a.get("href", "")
        if not title or len(title) < 12 or not link:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        if link.startswith("/"):
            # naive relative-to-absolute
            from urllib.parse import urljoin
            link = urljoin(url, link)
        out.append(
            NewsItem(
                title=title,
                link=link,
                source=source,
                published=None,
                guid=link,
            )
        )
        if len(out) >= limit:
            break
    return out
