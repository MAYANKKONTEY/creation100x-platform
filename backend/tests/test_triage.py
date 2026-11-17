import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import REPO_ROOT
from app.db import utcnow
from app.intelligence.clustering import jaccard, slugify_key, title_tokens
from app.intelligence.config import load_pipeline_config
from app.intelligence.triage import TriageService
from app.llm.base import LLMError, LLMRefusal
from app.models import Opportunity, RawItem, Source, Story
from app.scoring.models import load_scoring_config
from app.skills.loader import SkillLoader

SCORES = {"audience_relevance": 8, "business_importance": 6, "discussion_potential": 7,
          "virality_hypothesis": 5, "evidence_quality": 6}
REASONS = dict.fromkeys(SCORES, "reason")


@pytest.fixture
def cfg():
    return load_pipeline_config(REPO_ROOT / "config" / "pipeline.yaml")


@pytest.fixture
def service(fake_llm, cfg):
    return TriageService(fake_llm, SkillLoader(REPO_ROOT / ".claude" / "skills"), cfg,
                         load_scoring_config(REPO_ROOT / "config" / "scoring.yaml"))


def add_items(session, specs):
    """specs: list of (source_name, title, hours_ago)."""
    sources = {}
    items = []
    for i, (src, title, hours) in enumerate(specs):
        if src not in sources:
            sources[src] = Source(name=src, kind="rss", url=f"https://{src}.test/feed", category="A")
            session.add(sources[src])
            session.flush()
        item = RawItem(source_id=sources[src].id, url=f"https://{src}.test/{i}", url_hash=f"h{i}-{src}",
                       title=title, category="A",
                       published_at=None if hours is None else utcnow() - timedelta(hours=hours))
        session.add(item)
        items.append(item)
    session.flush()
    return items


def ids_in(prompt):
    items = json.loads(re.search(r"<items>(.*?)</items>", prompt, re.S).group(1))
    return [i["item_id"] for i in items]


def responder(overrides=None):
    """Build a TriageBatch for every item in the prompt; overrides: {item_id: dict}."""
    overrides = overrides or {}

    def respond(prompt):
        out = []
        for item_id in ids_in(prompt):
            base = {"item_id": item_id, "relevant": True, "category": "A", "pillar": "llms_agents",
                    "story_key": f"story-{item_id}", "sub_scores": dict(SCORES), "reasons": REASONS}
            o = overrides.get(item_id, {})
            if o.get("sub_scores"):
                base["sub_scores"] = {**SCORES, **o["sub_scores"]}
            base.update({k: v for k, v in o.items() if k != "sub_scores"})
            out.append(base)
        return {"items": out}
    return respond


def test_stale_items_are_never_sent(session, service, fake_llm):
    fresh, old = add_items(session, [("a", "Fresh agent news", 2), ("a", "Old news", 200)])
    fake_llm.queue_parse("TriageBatch", responder())
    stats = service.run(session)
    assert stats.stale_marked == 1 and old.triage_status == "stale"
    assert ids_in(fake_llm.calls[0]["prompt"]) == [fresh.id]
    assert fake_llm.calls[0]["effort"] == "low"
    assert "untrusted data" in fake_llm.calls[0]["system"]


def test_relevance_threshold_and_opportunity_creation(session, service, fake_llm):
    a, b, c = add_items(session, [("a", "Agent runtime launch", 1), ("a", "Celebrity gossip", 1), ("a", "Minor patch", 1)])
    fake_llm.queue_parse("TriageBatch", responder({
        b.id: {"relevant": False},
        c.id: {"sub_scores": {"audience_relevance": 3}},  # below min_audience_relevance=5
    }))
    stats = service.run(session)
    assert (a.triage_status, b.triage_status, c.triage_status) == ("relevant", "irrelevant", "irrelevant")
    assert stats.opportunities_created == 1
    opp = session.scalar(select(Opportunity))
    assert opp.pillar == "llms_agents" and opp.status == "scored"
    assert opp.sub_scores["freshness"] > 9.5  # computed, not judged
    assert a.triage["reasons"]["audience_relevance"] == "reason"
    assert opp.signals["coverage"] == {"items": 1, "distinct_sources": 1}


def test_same_story_key_merges_and_takes_best_scores(session, service, fake_llm):
    a, b = add_items(session, [("verge", "Google launches Gemini Tasks", 10), ("tc", "Gemini Tasks is now free for everyone", 1)])
    fake_llm.queue_parse("TriageBatch", responder({
        a.id: {"story_key": "Google Gemini Tasks launch", "sub_scores": {"evidence_quality": 4}},
        b.id: {"story_key": "google-gemini-tasks-launch", "sub_scores": {"evidence_quality": 9, "audience_relevance": 6}},
    }))
    stats = service.run(session)
    assert stats.stories_created == 1 and stats.stories_merged == 1
    assert session.query(Story).count() == 1 and session.query(Opportunity).count() == 1
    opp = session.scalar(select(Opportunity))
    assert opp.sub_scores["evidence_quality"] == 9 and opp.sub_scores["audience_relevance"] == 8
    assert opp.signals["coverage"] == {"items": 2, "distinct_sources": 2}
    story = session.scalar(select(Story))
    # freshness follows the newest item (1h old), not the first (10h old)
    assert opp.sub_scores["freshness"] > 9.8
    assert story.key == "google-gemini-tasks-launch"


def test_title_similarity_backstop_merges_across_runs(session, service, fake_llm):
    [a] = add_items(session, [("a", "OpenAI releases open-weight reasoning model gpt-oss", 3)])
    fake_llm.queue_parse("TriageBatch", responder({a.id: {"story_key": "openai-open-weights"}}))
    service.run(session)
    [b] = add_items(session, [("b", "OpenAI releases open-weight reasoning model gpt-oss today", 1)])
    fake_llm.queue_parse("TriageBatch", responder({b.id: {"story_key": "totally-different-key"}}))
    stats = service.run(session)
    assert stats.stories_merged == 1
    assert a.story_id == b.story_id
    # second prompt showed the existing story key so the model could reuse it
    assert "openai-open-weights" in fake_llm.calls[1]["prompt"]


def test_validation_rejects_bad_fields_and_ignores_unknown_ids(session, service, fake_llm):
    a, b, c = add_items(session, [("a", "One", 1), ("a", "Two", 1), ("a", "Three", 1)])

    def respond(prompt):
        good = responder({a.id: {"pillar": "astrology"}, b.id: {"sub_scores": {"business_importance": 11}}})(prompt)
        good["items"].append({**good["items"][2], "item_id": 99999})  # unknown id
        good["items"].append(good["items"][2])  # duplicate
        return good

    fake_llm.queue_parse("TriageBatch", respond)
    stats = service.run(session)
    assert a.triage_status == "error" and "pillar" in a.triage["error"]
    assert b.triage_status == "error" and "outside 0-10" in b.triage["error"]
    assert c.triage_status == "relevant"
    assert stats.invalid == 2 and stats.relevant == 1


def test_items_omitted_repeatedly_become_errors(session, service, fake_llm):
    [a] = add_items(session, [("a", "Ignored by model", 1)])
    for attempt in range(1, 4):
        fake_llm.queue_parse("TriageBatch", {"items": []})
        stats = service.run(session)
        assert stats.missing == 1
    assert a.triage_status == "error" and a.triage["attempts"] == 3


def test_batching_refusal_and_api_error(session, service, fake_llm, cfg):
    service.cfg = cfg.model_copy(update={"triage": cfg.triage.model_copy(update={"batch_size": 2})})
    items = add_items(session, [("a", f"Item {i}", i + 1) for i in range(5)])

    def refuse(prompt):
        raise LLMRefusal("other", "declined")

    def api_down(prompt):
        raise LLMError("Claude API error 529: overloaded")

    fake_llm.queue_parse("TriageBatch", responder())
    fake_llm.queue_parse("TriageBatch", refuse)
    fake_llm.queue_parse("TriageBatch", api_down)
    stats = service.run(session)
    assert stats.batches == 3 and stats.triaged == 2 and stats.refused == 2
    assert stats.llm_errors == ["Claude API error 529: overloaded"]
    statuses = [i.triage_status for i in items]
    assert statuses.count("relevant") == 2 and statuses.count("error") == 2 and statuses.count("pending") == 1


def test_clustering_helpers():
    assert slugify_key("Google Gemini: Tasks launch!") == "google-gemini-tasks-launch"
    assert slugify_key("!!!") == "story"
    assert title_tokens("Show HN: The new agent runtime") == {"agent", "runtime"}
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0 and jaccard(set(), {"a"}) == 0.0
