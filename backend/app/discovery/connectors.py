"""Discovery connectors: RSS/Atom feeds and the Hacker News Algolia search API.

Both use public, documented endpoints. HTTP is injected so tests run without network.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from app.discovery.base import DiscoveredItem, clean_text


class ConnectorError(RuntimeError):
    pass


def _get(http: httpx.Client, url: str, headers: dict | None = None) -> httpx.Response:
    try:
        resp = http.get(url, follow_redirects=True, headers=headers)
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


_SINCE = re.compile(r"\{since:(\d+)\}")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubSearchConnector:
    """Official GitHub search API (https://docs.github.com/rest/search/search).

    GitHub has no official "trending" endpoint. Source URLs search repositories created in the
    last N days (``{since:N}`` placeholder) sorted by stars. Stars/forks are stored as signals.
    """

    kind = "github_search"
    # The same name/description under this many owners is treated as a star-farmed clone network
    # and dropped before triage (observed live on 2026-11-17: 27 of the top 30 new "llm" repos).
    CLONE_DROP_OWNERS = 3

    def __init__(self, http: httpx.Client, token: str | None = None, now: Callable[[], datetime] | None = None):
        self.http = http
        self.token = token
        self.now = now or (lambda: datetime.now(UTC))
        self.last_skipped = 0

    def resolve_url(self, url: str) -> str:
        today = self.now().date()
        return _SINCE.sub(lambda m: (today - timedelta(days=int(m.group(1)))).isoformat(), url)

    def fetch(self, url: str, max_items: int) -> list[DiscoveredItem]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = _get(self.http, self.resolve_url(url), headers=headers).json()
        repos = (data.get("items") or [])[:max_items]
        # Star counts can be gamed. The same repo name or description under several owners in one
        # result set is a common sign of star-farmed clones; flag it (not drop) for triage.
        name_owners: dict[str, set] = {}
        desc_owners: dict[str, set] = {}
        for repo in repos:
            owner = (repo.get("owner") or {}).get("login")
            if repo.get("name"):
                name_owners.setdefault(repo["name"].lower(), set()).add(owner)
            if repo.get("description"):
                desc_owners.setdefault(repo["description"].strip().lower(), set()).add(owner)
        def owner_count(repo: dict) -> tuple[int, int]:
            return (
                len(name_owners.get((repo.get("name") or "").lower(), ())),
                len(desc_owners.get((repo.get("description") or "").strip().lower(), ())),
            )

        items: list[DiscoveredItem] = []
        self.last_skipped = 0
        for repo in repos:
            if max(owner_count(repo)) >= self.CLONE_DROP_OWNERS:
                self.last_skipped += 1
                continue
            html_url, name = repo.get("html_url"), repo.get("full_name")
            if not html_url or not name:
                continue
            desc = clean_text(repo.get("description"), 500)
            items.append(
                DiscoveredItem(
                    url=html_url,
                    title=f"{name}: {desc}" if desc else name,
                    summary=desc,
                    author=(repo.get("owner") or {}).get("login"),
                    published_at=_parse_iso(repo.get("created_at")),
                    signals={
                        "source": "github",
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "language": repo.get("language"),
                        "topics": (repo.get("topics") or [])[:10],
                        "stars_measured_at": self.now().isoformat(),
                        "flags": [
                            f
                            for f, hit in (
                                ("name_repeated_across_owners", owner_count(repo)[0] > 1),
                                ("description_repeated_across_owners", owner_count(repo)[1] > 1),
                            )
                            if hit
                        ],
                    },
                )
            )
        return items


def build_connectors(http: httpx.Client, github_token: str | None = None) -> dict[str, object]:
    return {
        c.kind: c
        for c in (RSSConnector(http), HNAlgoliaConnector(http), GitHubSearchConnector(http, token=github_token))
    }
