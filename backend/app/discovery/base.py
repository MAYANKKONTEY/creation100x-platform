"""Connector interface and URL normalisation for discovery sources."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = re.compile(r"^(utm_[a-z]+|ref|ref_src|fbclid|gclid|mc_cid|mc_eid|igshid|si)$", re.I)


@dataclass
class DiscoveredItem:
    url: str
    title: str
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    signals: dict = field(default_factory=dict)  # source-provided metrics only


class Connector(Protocol):
    kind: str

    def fetch(self, url: str, max_items: int) -> list[DiscoveredItem]: ...


def normalize_url(url: str) -> str:
    """Lower-case scheme/host, drop fragments, tracking params and trailing slash; sort the query."""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_text(value: str | None, limit: int = 2000) -> str | None:
    if not value:
        return None
    text = _WS.sub(" ", html.unescape(_TAGS.sub(" ", value))).strip()
    return text[:limit] or None
