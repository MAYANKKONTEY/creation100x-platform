from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.db import Database
from app.llm.fake import FakeLLM

FIXTURES = Path(__file__).parent / "fixtures"

FEEDS = {
    "https://feeds.test/rss": ("application/rss+xml", (FIXTURES / "rss.xml").read_bytes()),
    "https://feeds.test/atom": ("application/atom+xml", (FIXTURES / "atom.xml").read_bytes()),
    "https://hn.test/api": ("application/json", (FIXTURES / "hn.json").read_bytes()),
}


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url in FEEDS:
        ctype, body = FEEDS[url]
        return httpx.Response(200, content=body, headers={"content-type": ctype})
    if url == "https://feeds.test/broken":
        return httpx.Response(500, text="boom")
    return httpx.Response(404, text="not found")


@pytest.fixture
def http_client():
    with httpx.Client(transport=httpx.MockTransport(_handler)) as c:
        yield c


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        anthropic_api_key=None,
        publishing_enabled=False,
        config_dir=REPO_ROOT / "config",
        skills_dir=REPO_ROOT / ".claude" / "skills",
    )


@pytest.fixture
def db(settings) -> Database:
    d = Database(settings.database_url)
    d.create_all()
    return d


@pytest.fixture
def session(db):
    with db.session() as s:
        yield s


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(settings, db, http_client, fake_llm):
    from app.api.main import create_app

    def factory(_settings, recorder):
        fake_llm.on_usage = recorder
        return fake_llm

    app = create_app(settings=settings, db=db, llm_factory=factory, http_client=http_client)
    with TestClient(app) as c:
        yield c
