"""API tests for Milestone 2 routes (FakeLLM, mocked HTTP)."""

import json
import re

SCORES = {"audience_relevance": 8, "business_importance": 6, "discussion_potential": 7,
          "virality_hypothesis": 5, "evidence_quality": 6}


def triage_responder(category_by_title=None):
    category_by_title = category_by_title or {}

    def respond(prompt):
        items = json.loads(re.search(r"<items>(.*?)</items>", prompt, re.S).group(1))
        out = []
        for i in items:
            cat = next((c for k, c in category_by_title.items() if k in i["title"]), "A")
            out.append({"item_id": i["item_id"], "relevant": True, "category": cat,
                        "pillar": "business_models" if cat == "B" else "llms_agents",
                        "story_key": re.sub(r"[^a-z0-9]+", "-", i["title"].lower())[:40],
                        "sub_scores": SCORES, "reasons": dict.fromkeys(SCORES, "r")})
        return {"items": out}
    return respond


ANALYSIS = {
    "why_it_matters": "m", "why_people_discuss": "d", "audience_pain_point": "p", "original_angle": "o",
    "contrarian_angle": "c", "educational_angle": "e", "business_implication": "b", "visual_direction": "v",
    "suggested_formats": ["technical"], "research_questions": ["q"], "sensitive": False, "sensitivity_reasons": [],
}


def _setup_sources(client):
    client.post("/api/sources", json={"name": "rss", "kind": "rss", "url": "https://feeds.test/rss"})
    client.post("/api/sources", json={"name": "gh", "kind": "github_search",
                                      "url": "https://api.github.test/search/repositories?q=topic:llm+created:>{since:7}"})


def test_seed_includes_github_sources(client):
    client.post("/api/sources/seed")
    kinds = {s["kind"] for s in client.get("/api/sources").json()}
    assert kinds == {"rss", "hn_algolia", "github_search"}


def test_triage_requires_llm(settings, db, http_client):
    from fastapi.testclient import TestClient

    from app.api.main import create_app

    with TestClient(create_app(settings=settings, db=db, http_client=http_client)) as c:
        assert c.post("/api/triage/run").status_code == 503
        assert c.post("/api/pipeline/run").status_code == 503


def test_pipeline_end_to_end_and_radars(client, fake_llm):
    client.post("/api/sources", json={"name": "fresh", "kind": "rss", "url": "https://feeds.test/fresh"})
    fake_llm.queue_parse("TriageBatch", triage_responder({"SaaS pricing": "B"}))
    for _ in range(5):
        fake_llm.queue_parse("OpportunityAnalysis", ANALYSIS)

    r = client.post("/api/pipeline/run", json={"discover": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["discovery"]["sources_ok"] == 1 and out["discovery"]["items_new"] == 2
    assert out["triage"]["triaged"] == 2 and out["triage"]["opportunities_created"] == 2
    assert out["analysis"]["analyzed"] == 2 and len(out["selected_opportunity_ids"]) == 2

    trends = client.get("/api/radar/trends", params={"days": 30}).json()
    business = client.get("/api/radar/business", params={"days": 30}).json()
    assert len(trends) == 1 and trends[0]["story"]["category"] == "A"
    assert len(business) == 1 and business[0]["story"]["category"] == "B"
    assert business[0]["opportunity"]["pillar"] == "business_models"
    for entry in trends + business:
        assert entry["coverage"]["items"] >= 1
        if entry["opportunity"]:
            assert entry["opportunity"]["score_breakdown"]["disclaimer"].startswith("Heuristic")

    detail = client.get(f"/api/stories/{trends[0]['story']['id']}").json()
    assert detail["items"][0]["triage_status"] == "relevant"
    assert detail["opportunity"]["status"] == "analyzed"
    assert client.get("/api/stories/9999").status_code == 404

    jobs = client.get("/api/jobs").json()
    assert jobs[0]["name"] == "intelligence_pipeline" and jobs[0]["status"] == "succeeded"
    purposes = {c["purpose"] for c in client.get("/api/llm-calls").json()}
    assert "triage" in purposes


def test_triage_endpoint_and_manual_analyze(client, fake_llm):
    client.post("/api/sources", json={"name": "fresh", "kind": "rss", "url": "https://feeds.test/fresh"})
    _setup_sources(client)
    assert client.post("/api/discovery/run").json()["sources_ok"] == 3
    fake_llm.queue_parse("TriageBatch", triage_responder())
    r = client.post("/api/triage/run", json={"max_items": 50}).json()
    assert r["triaged"] >= 2  # the two fresh items at least; fixed-date fixtures may be stale
    opps = client.get("/api/opportunities", params={"pillar": "llms_agents"}).json()
    assert opps and all(o["pillar"] == "llms_agents" for o in opps)
    fake_llm.queue_parse("OpportunityAnalysis", ANALYSIS)
    analyzed = client.post(f"/api/opportunities/{opps[0]['id']}/analyze").json()
    assert analyzed["status"] == "analyzed" and analyzed["analysis"]["verified"] is False
    assert client.post("/api/opportunities/9999/analyze").status_code == 404
    items = client.get("/api/items", params={"triage_status": "relevant"}).json()
    assert items and all(i["triage_status"] == "relevant" for i in items)


def test_swipe_file_flow(client, fake_llm):
    text = ("Most teams adding AI agents start with twenty tools and wonder why nothing works. "
            "We cut ours to three. Here is the checklist.")
    r = client.post("/api/swipe-file", json={"text": text, "author_name": "A. Writer",
                                             "url": "https://www.linkedin.com/posts/example",
                                             "owner_reported_metrics": {"reactions": 1200}})
    assert r.status_code == 201
    post_id = r.json()["id"]
    assert client.post("/api/swipe-file", json={"text": "too short"}).status_code == 422
    assert client.post("/api/swipe-file", json={"text": text, "owner_reported_metrics": {"reactions": "lots"}}).status_code == 422

    fake_llm.queue_parse("PostPattern", {
        "topic": "agent tools", "hook_type": "contrarian", "first_line_mechanism": "Names a common mistake",
        "structure": ["mistake", "result", "artifact"], "format": "founder_lessons",
        "visual_hierarchy": "short lines", "educational_value": "checklist", "discussion_trigger": "asks for counts",
        "why_it_may_have_resonated": "number contrast", "reusable_template": "Most {audience} {mistake}. {fix}.",
    })
    analyzed = client.post(f"/api/swipe-file/{post_id}/analyze").json()
    assert analyzed["analysis_status"] == "analyzed"
    assert client.get("/api/patterns").json()["hook_types"] == {"contrarian": 1}
    assert client.post("/api/swipe-file/999/analyze").status_code == 404
    assert len(client.get("/api/swipe-file").json()) == 1


def test_pipeline_config_endpoint(client):
    cfg = client.get("/api/pipeline/config").json()
    assert len(cfg["pillars"]) == 10 and cfg["triage"]["effort"] == "low"
