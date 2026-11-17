from datetime import UTC, datetime

import httpx

from app.discovery.connectors import GitHubSearchConnector, build_connectors

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
URL = "https://api.github.test/search/repositories?q=topic:llm+created:>{since:7}&sort=stars"


def test_since_placeholder_resolves_to_date():
    c = GitHubSearchConnector(httpx.Client(), now=lambda: NOW)
    assert c.resolve_url(URL) == "https://api.github.test/search/repositories?q=topic:llm+created:>2026-11-10&sort=stars"


def test_fetch_parses_repos_and_sends_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        from tests.conftest import FIXTURES
        return httpx.Response(200, content=(FIXTURES / "github.json").read_bytes())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        connector = GitHubSearchConnector(http, token="tok123", now=lambda: NOW)
        items = connector.fetch(URL, 10)

    assert "created:%3E2026-11-10" in seen["url"] or "created:>2026-11-10" in seen["url"]
    assert seen["headers"]["authorization"] == "Bearer tok123"
    assert seen["headers"]["accept"] == "application/vnd.github+json"
    assert len(items) == 4  # entry without name/url skipped
    first = items[0]
    assert first.title == "acme/agent-kit: Minimal agent runtime with 3 tools"
    assert first.published_at == datetime(2026, 11, 14, 8, tzinfo=UTC)
    assert first.signals["stars"] == 2140 and first.signals["source"] == "github"
    assert first.signals["stars_measured_at"] == NOW.isoformat()
    assert items[1].title == "solo/no-desc"
    assert first.signals["flags"] == []
    assert items[2].signals["flags"] == ["name_repeated_across_owners", "description_repeated_across_owners"]
    # three owners sharing one name: a clone network, dropped and counted
    assert connector.last_skipped == 3
    assert not any("Wallet-Booster" in i.title for i in items)


def test_no_token_means_no_auth_header(http_client):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"items": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert GitHubSearchConnector(http).fetch(URL, 5) == []
    assert seen["auth"] is None


def test_registered_in_build_connectors(http_client):
    assert set(build_connectors(http_client)) == {"rss", "hn_algolia", "github_search"}
