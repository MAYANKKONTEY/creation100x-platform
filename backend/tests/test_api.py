from app.llm.base import SearchResult, WebSource, Citation
from app.research.service import ResearchExtraction


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok" and body["llm_configured"] is False
    assert body["publishing_can_publish"] is False and body["skills"] == 13


def test_sources_crud_and_seed(client):
    r = client.post("/api/sources", json={"name": "Test RSS", "kind": "rss", "url": "https://feeds.test/rss", "category": "B"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.post("/api/sources", json={"name": "Test RSS", "kind": "rss", "url": "https://feeds.test/rss"}).status_code == 409
    assert client.post("/api/sources", json={"name": "Bad", "kind": "scraper", "url": "https://x.test"}).status_code == 422
    r = client.patch(f"/api/sources/{sid}", json={"enabled": False})
    assert r.json()["enabled"] is False
    assert client.post("/api/sources/seed").json()["added"] >= 10


def test_discovery_items_and_opportunity_scoring(client):
    client.post("/api/sources", json={"name": "rss", "kind": "rss", "url": "https://feeds.test/rss"})
    client.post("/api/sources", json={"name": "hn", "kind": "hn_algolia", "url": "https://hn.test/api"})
    run = client.post("/api/discovery/run").json()
    assert run["items_new"] == 4 and run["sources_failed"] == 0

    items = client.get("/api/items", params={"q": "agent"}).json()
    assert len(items) == 1 and items[0]["signals"]["points"] == 420

    opp = client.post("/api/opportunities", json={"raw_item_id": items[0]["id"]}).json()
    assert opp["title"].startswith("Show HN") and opp["status"] == "new"

    judged = {"audience_relevance": 9, "business_importance": 7, "discussion_potential": 8,
              "virality_hypothesis": 6, "evidence_quality": 5}
    # freshness may not be supplied by the caller
    assert client.post(f"/api/opportunities/{opp['id']}/score", json={**judged, "freshness": 10}).status_code == 422
    scored = client.post(f"/api/opportunities/{opp['id']}/score", json=judged).json()
    assert scored["status"] == "scored"
    assert 0 <= scored["sub_scores"]["freshness"] <= 10
    assert scored["score_breakdown"]["disclaimer"].startswith("Heuristic")
    assert scored["scoring_version"]

    listed = client.get("/api/opportunities", params={"min_score": 1}).json()
    assert [o["id"] for o in listed] == [opp["id"]]
    assert client.get("/api/jobs").json()[0]["name"] == "discovery"


def test_manual_opportunity_requires_title_and_category(client):
    assert client.post("/api/opportunities", json={}).status_code == 422
    assert client.post("/api/opportunities", json={"raw_item_id": 999}).status_code == 404
    r = client.post("/api/opportunities", json={"title": "Open vs closed models", "category": "A"})
    assert r.status_code == 201


def test_research_endpoint_records_llm_calls(client, fake_llm):
    fake_llm.queue_search(SearchResult(
        text="notes", sources=[WebSource("https://dev.example/survey", "Survey")],
        citations=[Citation("https://dev.example/survey", "Most developers now use AI coding assistants every week")],
    ))
    fake_llm.queue_parse("ResearchExtraction", ResearchExtraction(summary="s", claims=[
        {"text": "Most developers now use AI coding assistants every week", "claim_type": "fact",
         "source_urls": ["https://dev.example/survey"],
         "supporting_quote": "developers now use AI coding assistants every week"},
    ]))
    r = client.post("/api/research", json={"topic": "AI coding assistant adoption"})
    assert r.status_code == 201, r.text
    brief = r.json()
    assert brief["claims"][0]["status"] == "verified"
    assert brief["status"] == "weak_evidence"  # fewer than 2 verified claims
    assert client.get(f"/api/research/{brief['id']}").json()["topic"] == "AI coding assistant adoption"
    calls = client.get("/api/llm-calls").json()
    assert {c["purpose"] for c in calls} == {"research.gather", "research.extract"}


def test_research_returns_503_without_llm(settings, db, http_client):
    from fastapi.testclient import TestClient

    from app.api.main import create_app

    app = create_app(settings=settings, db=db, http_client=http_client)  # real factory, no key
    with TestClient(app) as c:
        r = c.post("/api/research", json={"topic": "anything at all"})
    assert r.status_code == 503


def test_safety_endpoints(client):
    assert client.get("/api/safety").json()["can_publish"] is False
    assert client.post("/api/safety/enable-publishing", json={"confirm": "yes", "reason": "going live"}).status_code == 400
    r = client.post("/api/safety/enable-publishing", json={"confirm": "ENABLE PUBLISHING", "reason": "ready"}).json()
    assert r["db_enabled"] is True and r["can_publish"] is False  # env flag still off
    r = client.post("/api/safety/emergency-stop", json={"reason": "bad draft"}).json()
    assert r["db_enabled"] is False and "EMERGENCY" in r["reason"]


def test_brand_voice_samples(client):
    assert client.post("/api/brand-voice/samples", json={"text": "too short"}).status_code == 422
    text = "I spent the weekend testing three agent frameworks. Here is what broke first, and why it matters."
    assert client.post("/api/brand-voice/samples", json={"text": text, "source": "draft"}).status_code == 201
    assert len(client.get("/api/brand-voice/samples").json()) == 1


def test_skills_endpoint_reports_no_problems(client):
    skills = client.get("/api/skills").json()
    assert len(skills) == 13
    assert all(s["problems"] == [] for s in skills)


def test_scoring_models_endpoint(client):
    body = client.get("/api/scoring/models").json()
    assert set(body["models"]) == {"content_opportunity", "post_quality", "visual_quality"}


def test_timestamps_are_utc(client):
    client.post("/api/sources", json={"name": "rss", "kind": "rss", "url": "https://feeds.test/rss"})
    client.post("/api/discovery/run")
    item = client.get("/api/items").json()[0]
    assert item["fetched_at"].endswith("Z") or item["fetched_at"].endswith("+00:00")
