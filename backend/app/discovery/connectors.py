"""Discovery connectors: RSS/Atom feeds and the Hacker News Algolia search API.

Both use public, documented endpoints. HTTP is injected so tests run without network.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime

import feedparser
import httpx

from app.discovery.base import DiscoveredItem, clean_text


class ConnectorError(RuntimeError):
    pass


def _get(http: httpx.Client, url: str) -> httpx.Response:
    try:
        resp = http.get(url, follow_redirects=True)
    except httpx.HTTPError as e:
        raise ConnectorError(f"GET {url} failed: {type(e).__name__}") from e
    if resp.status_code >= 400:
        raise ConnectorError(f"GET {url} returned HTTP {resp.status_code}")
    return resp


def _struct_to_dt(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)


class RSSConnector:
    kind = "rss"

    def __init__(self, http: httpx.Client):
        self.http = http

    def fetch(self, url: str, max_items: int) -> list[DiscoveredItem]:
        resp = _get(self.http, url)
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            raise ConnectorError(f"Unparseable feed at {url}: {feed.bozo_exception!r}")
        items: list[DiscoveredItem] = []
        for entry in feed.entries[:max_items]:
            link = entry.get("link")
            title = clean_text(entry.get("title"), 500)
            if not link or not title:
                continue
            items.append(
                DiscoveredItem(
                    url=link,
                    title=title,
                    summary=clean_text(entry.get("summary") or entry.get("description")),
                    author=clean_text(entry.get("author"), 300),
                    published_at=_struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed")),
                )
            )
        return items


class HNAlgoliaConnector:
    """https://hn.algolia.com/api - public HN search API. Points/comments stored as source signals."""

    kind = "hn_algolia"

    def __init__(self, http: httpx.Client):
        self.http = http

    def fetch(self, url: str, max_items: int) -> list[DiscoveredItem]:
        data = _get(self.http, url).json()
        items: list[DiscoveredItem] = []
        for hit in (data.get("hits") or [])[:max_items]:
            object_id = hit.get("objectID")
            title = clean_text(hit.get("title"), 500)
            if not title or not object_id:
                continue
            discussion = f"https://news.ycombinator.com/item?id={object_id}"
            ts = hit.get("created_at_i")
            items.append(
                DiscoveredItem(
                    url=hit.get("url") or discussion,
                    title=title,
                    summary=clean_text(hit.get("story_text")),
                    author=hit.get("author"),
                    published_at=datetime.fromtimestamp(ts, tz=UTC) if ts else None,
                    signals={
                        "source": "hacker_news",
                        "points": hit.get("points"),
                        "comments": hit.get("num_comments"),
                        "discussion_url": discussion,
                    },
                )
            )
        return items


def build_connectors(http: httpx.Client) -> dict[str, object]:
    return {c.kind: c for c in (RSSConnector(http), HNAlgoliaConnector(http))}
