from datetime import UTC, datetime

from sqlalchemy import select

from app.discovery.base import clean_text, normalize_url, url_hash
from app.discovery.connectors import ConnectorError, HNAlgoliaConnector, RSSConnector, build_connectors
from app.discovery.ingest import ingest, seed_sources
from app.models import RawItem, Source
from app.config import REPO_ROOT

import pytest


def test_normalize_url_strips_tracking_fragment_www_and_slash():
    a = normalize_url("https://WWW.Example.com/news/model/?utm_source=x&id=7#top")
    b = normalize_url("https://example.com/news/model?id=7&utm_medium=email")
    assert a == b == "https://example.com/news/model?id=7"
    assert url_hash("https://example.com/a?b=1&c=2") == url_hash("https://example.com/a?c=2&b=1")


def test_clean_text():
    assert clean_text("<p>A &amp; <b>B</b>\n  C</p>") == "A & B C"
    assert clean_text("") is None
    assert len(clean_text("x" * 5000, limit=100)) == 100


def test_rss_connector_parses_items(http_client):
    items = RSSConnector(http_client).fetch("https://feeds.test/rss", 50)
    assert [i.title for i in items] == [
        "Open-weight model tops coding benchmark", "Same story, different tracking", "SaaS pricing shifts to usage-based",
    ]  # entry with empty title skipped
    assert items[0].summary == "A new open-weight model & its results."
    assert items[0].published_at == datetime(2026, 11, 16, 9, tzinfo=UTC)
    assert items[2].published_at is None
    assert items[0].signals == {}  # RSS provides no engagement metrics; none invented


def test_atom_connector(http_client):
    [item] = RSSConnector(http_client).fetch("https://feeds.test/atom", 10)
    assert item.url == "https://blog.example.org/agents"
    assert item.author == "Jane Writer"
    assert item.published_at == datetime(2026, 11, 15, 12, tzinfo=UTC)


def test_rss_max_items(http_client):
    assert len(RSSConnector(http_client).fetch("https://feeds.test/rss", 1)) == 1


def test_connector_http_error(http_client):
    with pytest.raises(ConnectorError, match="HTTP 500"):
        RSSConnector(http_client).fetch("https://feeds.test/broken", 10)


def test_hn_connector_signals_and_fallback_url(http_client):
    items = HNAlgoliaConnector(http_client).fetch("https://hn.test/api", 50)
    assert len(items) == 2
    assert items[0].signals["points"] == 420 and items[0].signals["comments"] == 180
    assert items[1].url == "https://news.ycombinator.com/item?id=112"  # Ask HN has no external URL
    assert items[1].summary == "Curious how people price"


def _add_sources(session):
    session.add_all([
        Source(name="rss", kind="rss", url="https://feeds.test/rss", category="A"),
        Source(name="atom", kind="rss", url="https://feeds.test/atom", category="A"),
        Source(name="hn", kind="hn_algolia", url="https://hn.test/api", category="A"),
        Source(name="broken", kind="rss", url="https://feeds.test/broken", category="B"),
        Source(name="mystery", kind="carrier_pigeon", url="https://x.test", category="B"),
        Source(name="off", kind="rss", url="https://feeds.test/rss", category="B", enabled=False),
    ])
    session.flush()


def test_ingest_dedupes_and_isolates_failures(session, http_client):
    _add_sources(session)
    stats = ingest(session, build_connectors(http_client))
    assert stats.sources_ok == 3 and stats.sources_failed == 2
    assert set(stats.errors) == {"broken", "mystery"}
    # rss: 3 entries, 2 are the same story after URL normalisation -> 2 new; atom 1; hn 2
    assert stats.items_new == 5
    broken = session.scalar(select(Source).where(Source.name == "broken"))
    assert "HTTP 500" in broken.last_error

    again = ingest(session, build_connectors(http_client))
    assert again.items_new == 0
    assert session.query(RawItem).count() == 5


def test_seed_sources_is_idempotent(session):
    path = REPO_ROOT / "config" / "sources.yaml"
    first = seed_sources(session, path)
    assert first >= 10
    assert seed_sources(session, path) == 0
