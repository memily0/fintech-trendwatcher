"""Small RSS ingestion helper using only the Python standard library."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree


DEFAULT_RSS_SOURCES: dict[str, str] = {
    "Finextra": "https://www.finextra.com/rss/news.aspx",
    "TechCrunch Fintech": "https://techcrunch.com/tag/fintech/feed/",
    "The Paypers": "https://thepaypers.com/rss",
}


def _text(node: ElementTree.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return " ".join(node.text.split())


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def fetch_rss_articles(
    sources: dict[str, str] | None = None,
    limit_per_source: int = 12,
    timeout: int = 12,
) -> list[dict[str, str]]:
    """Fetch a small batch of RSS articles.

    This is optional for the MVP. The app still works without network access by
    using the built-in demo dataset.
    """

    articles: list[dict[str, str]] = []
    for source, feed_url in (sources or DEFAULT_RSS_SOURCES).items():
        req = Request(feed_url, headers={"User-Agent": "fintech-trendwatcher-mvp/1.0"})
        try:
            with urlopen(req, timeout=timeout) as response:
                data = response.read()
            root = ElementTree.fromstring(data)
        except Exception:
            continue

        items: Iterable[ElementTree.Element] = root.findall(".//item")
        for idx, item in enumerate(items):
            if idx >= limit_per_source:
                break
            title = _text(item.find("title"))
            link = _text(item.find("link"))
            description = _text(item.find("description"))
            published = _parse_date(_text(item.find("pubDate"))) or datetime.utcnow().date().isoformat()
            if title and link:
                articles.append(
                    {
                        "id": f"rss-{source.lower().replace(' ', '-')}-{idx + 1}",
                        "title": title,
                        "url": link,
                        "source": source,
                        "published_at": published,
                        "snippet": description,
                        "text": description,
                    }
                )
    return articles
