"""Small RSS ingestion helper using only the Python standard library."""

from __future__ import annotations

import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree


DEFAULT_RSS_SOURCES: dict[str, str] = {
    "Банк России — новости": "https://www.cbr.ru/rss/RssNews",
    "Банк России — события": "https://www.cbr.ru/rss/eventrss",
    "Банк России — пресс-релизы": "https://www.cbr.ru/rss/RssPress",
    "РБК — новости": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "Finextra": "https://www.finextra.com/rss/headlines.aspx",
    "TechCrunch Fintech": "https://techcrunch.com/tag/fintech/feed/",
    "PYMNTS": "https://www.pymnts.com/feed/",
    "Stripe Blog": "https://stripe.com/blog/feed.rss",
}


def clean_rss_text(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\xa0", " ")
    return " ".join(value.split())


def _text(node: ElementTree.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return clean_rss_text(node.text)


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return ""


def _first_text(item: ElementTree.Element, selectors: list[str]) -> str:
    for selector in selectors:
        value = _text(item.find(selector))
        if value:
            return value
    return ""


def _link(item: ElementTree.Element) -> str:
    link = _text(item.find("link"))
    if link:
        return link
    atom_link = item.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is not None:
        return atom_link.attrib.get("href", "")
    return ""


def _items(root: ElementTree.Element) -> Iterable[ElementTree.Element]:
    rss_items = root.findall(".//item")
    if rss_items:
        return rss_items
    return root.findall(".//{http://www.w3.org/2005/Atom}entry")


def fetch_rss_articles_with_status(
    sources: dict[str, str] | None = None,
    limit_per_source: int = 12,
    timeout: int = 12,
) -> tuple[list[dict[str, str]], list[str]]:
    """Fetch RSS articles and return non-fatal source errors."""

    articles: list[dict[str, str]] = []
    warnings: list[str] = []
    for source, feed_url in (sources or DEFAULT_RSS_SOURCES).items():
        req = Request(feed_url, headers={"User-Agent": "fintech-trendwatcher-mvp/1.0"})
        try:
            with urlopen(req, timeout=timeout) as response:
                data = response.read()
            root = ElementTree.fromstring(data)
        except Exception as exc:
            warnings.append(f"{source}: RSS не загрузился ({exc})")
            continue

        source_count = 0
        for idx, item in enumerate(_items(root)):
            if source_count >= limit_per_source:
                break
            title = _first_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
            link = _link(item)
            description = _first_text(
                item,
                [
                    "description",
                    "summary",
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                ],
            )
            published_raw = _first_text(
                item,
                [
                    "pubDate",
                    "published",
                    "updated",
                    "{http://purl.org/dc/elements/1.1/}date",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ],
            )
            published = _parse_date(published_raw) or datetime.utcnow().date().isoformat()
            if title and link:
                source_count += 1
                articles.append(
                    {
                        "id": f"rss-{source.lower().replace(' ', '-')}-{idx + 1}",
                        "title": clean_rss_text(title),
                        "url": link,
                        "source": source,
                        "published_at": published,
                        "snippet": clean_rss_text(description),
                        "text": clean_rss_text(description),
                    }
                )
        if source_count == 0:
            warnings.append(f"{source}: RSS загрузился, но публикации не найдены")
    return articles, warnings


def fetch_rss_articles(
    sources: dict[str, str] | None = None,
    limit_per_source: int = 12,
    timeout: int = 12,
) -> list[dict[str, str]]:
    """Fetch a small batch of RSS articles.

    This is optional for the MVP. The app still works without network access by
    using the built-in demo dataset.
    """

    articles, _warnings = fetch_rss_articles_with_status(sources, limit_per_source, timeout)
    return articles
