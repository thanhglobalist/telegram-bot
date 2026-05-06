"""Daily news fetcher. Supports RSS feeds and falls back to plain HTML scraping."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Use a realistic browser UA — some sources (e.g. Investing.com) reject bot UAs.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    # vi first — some VN sites (e.g. VnExpress) 406 on bare en-US.
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
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


@dataclass
class FullArticle:
    """A news article with full body + main image, ready for review/broadcast."""
    guid: str
    title: str
    link: str
    source: str
    body: str          # plain text, paragraphs separated by \n\n
    image_url: str | None
    published: datetime | None


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


def fetch_full_article(item: NewsItem) -> FullArticle:
    """Download an article page and extract main image + body text.

    Strategy:
      1) Pull <meta property="og:image"> for the main image.
      2) For body: prefer <article>; otherwise the largest text container
         (<main>, <div role="main">, or the densest <div>).
      3) Strip nav/scripts/styles/figures, keep paragraphs.
    """
    with httpx.Client(
        timeout=TIMEOUT,
        headers=BROWSER_HEADERS,
        follow_redirects=True,
    ) as c:
        r = c.get(item.link)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # --- Main image ---
    image_url: str | None = None
    for sel, attr in [
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[name="twitter:image:src"]', "content"),
        ('link[rel="image_src"]', "href"),
    ]:
        tag = soup.select_one(sel)
        if tag and tag.get(attr):
            image_url = tag[attr].strip()
            break
    if not image_url:
        # Fall back to first sizable <img> inside an <article>
        first_img = soup.select_one("article img[src], main img[src]")
        if first_img:
            image_url = first_img.get("src", "").strip() or None
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url
    elif image_url and image_url.startswith("/"):
        from urllib.parse import urljoin
        image_url = urljoin(item.link, image_url)

    # --- Body text ---
    # Strip junk first
    for junk in soup.select(
        "script, style, nav, header, footer, aside, form, iframe, noscript, "
        ".advertisement, .ad, [class*='related'], [class*='newsletter'], "
        "[class*='subscribe'], [class*='social'], [class*='share']"
    ):
        junk.decompose()

    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", attrs={"role": "main"})
    )
    if container is None:
        # Pick the <div> with the most <p> tags as a heuristic
        candidates = soup.find_all("div")
        container = max(
            candidates,
            key=lambda d: len(d.find_all("p")),
            default=soup.body or soup,
        )

    paragraphs: list[str] = []
    for p in container.find_all(["p", "h2", "h3"]):
        text = p.get_text(" ", strip=True)
        if not text or len(text) < 30:
            continue
        # Skip cookie/subscribe banners
        low = text.lower()
        if any(bad in low for bad in (
            "cookie", "subscribe to our newsletter", "sign up to",
            "all rights reserved",
        )):
            continue
        paragraphs.append(text)

    body = "\n\n".join(paragraphs).strip()
    if not body:
        body = "(Could not extract article body. Tap the link to read on the source site.)"

    return FullArticle(
        guid=item.guid,
        title=item.title,
        link=item.link,
        source=item.source,
        body=body,
        image_url=image_url,
        published=item.published,
    )


def _fetch_html(url: str, limit: int) -> list[NewsItem]:
    """Very generic fallback: pulls the first N <article>/<h2>/<h3> headlines."""
    with httpx.Client(timeout=TIMEOUT, headers=BROWSER_HEADERS, follow_redirects=True) as c:
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
