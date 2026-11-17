import pytest

from app.config import REPO_ROOT
from app.intelligence.analysis import AnalysisService, OpportunityAnalysis, select_balanced
from app.intelligence.config import load_pipeline_config
from app.intelligence.swipe import analyze_swipe_post, copied_ngrams, pattern_summary, PostPattern
from app.llm.base import LLMError, LLMRefusal
from app.models import Opportunity, SwipePost
from app.skills.loader import SkillLoader

SKILLS = SkillLoader(REPO_ROOT / ".claude" / "skills")


def _analysis(**kw):
    base = dict(
        why_it_matters="m", why_people_discuss="d", audience_pain_point="p", original_angle="o",
        contrarian_angle="c", educational_angle="e", business_implication="b", visual_direction="v",
        suggested_formats=["technical", "horoscope"], research_questions=["Is the benchmark self-reported?"],
        sensitive=False, sensitivity_reasons=[],
    )
    base.update(kw)
    return OpportunityAnalysis(**base)


def _opp(session, title="Agent runtime", pillar="llms_agents", score=70):
    o = Opportunity(title=title, category="A", pillar=pillar, score_total=score, status="scored")
    session.add(o)
    session.flush()
    return o


def test_select_balanced_caps_per_pillar_without_padding(session):
    opps = [_opp(session, f"o{i}", p, s) for i, (p, s) in enumerate(
        [("llms_agents", 90), ("llms_agents", 85), ("llms_agents", 80), ("business_models", 60), ("marketing_distribution", 50)])]
    picked = select_balanced(opps, top_n=4, max_per_pillar=2)
    assert [o.title for o in picked] == ["o0", "o1", "o3", "o4"]
    assert len(select_balanced(opps[:3], top_n=5, max_per_pillar=2)) == 2


@pytest.fixture
def analysis_service(fake_llm):
    return AnalysisService(fake_llm, SKILLS, load_pipeline_config(REPO_ROOT / "config" / "pipeline.yaml"))


def test_analyze_stores_unverified_analysis_and_filters_formats(session, analysis_service, fake_llm):
    opp = _opp(session)
    fake_llm.queue_parse("OpportunityAnalysis", _analysis())
    analysis_service.analyze(session, opp)
    assert opp.status == "analyzed"
    assert opp.analysis["basis"] == "headlines_and_summaries" and opp.analysis["verified"] is False
    assert opp.analysis["suggested_formats"] == ["technical"] and opp.analysis["dropped_formats"] == ["horoscope"]
    call = fake_llm.calls[0]
    assert call["effort"] == "medium"
    assert '<skill name="controversial-angle">' in call["system"]


def test_sensitive_or_refused_goes_to_review(session, analysis_service, fake_llm):
    a, b = _opp(session, "Layoffs at X"), _opp(session, "Something")
    fake_llm.queue_parse("OpportunityAnalysis", _analysis(sensitive=True, sensitivity_reasons=["named-company layoffs"]))

    def refuse(_):
        raise LLMRefusal("other", "no")

    fake_llm.queue_parse("OpportunityAnalysis", refuse)
    analysis_service.analyze(session, a)
    analysis_service.analyze(session, b)
    assert a.status == "needs_review" and b.status == "needs_review"
    assert "declined" in b.analysis["error"]


def test_analyze_selected_skips_done_and_stops_on_api_error(session, analysis_service, fake_llm):
    done = _opp(session, "done", "llms_agents", 99)
    done.analysis = {"analyzed_at": "2026-11-17T00:00:00"}
    first = _opp(session, "first", "business_models", 80)
    second = _opp(session, "second", "marketing_distribution", 70)
    fake_llm.queue_parse("OpportunityAnalysis", _analysis())

    def down(_):
        raise LLMError("overloaded")

    fake_llm.queue_parse("OpportunityAnalysis", down)
    picked, stats = analysis_service.analyze_selected(session, [done, first, second])
    assert [o.title for o in picked] == ["done", "first", "second"]
    assert stats.analyzed == 1 and stats.llm_errors == ["overloaded"]
    assert first.status == "analyzed" and second.status == "scored"


POST = (
    "Most teams adding AI agents start with twenty tools and wonder why nothing works. "
    "We cut ours to three and reliability went up overnight. Here is the checklist we use now."
)


def _pattern(**kw):
    base = dict(
        topic="agent tool count", hook_type="contrarian",
        first_line_mechanism="Names a common mistake the reader probably makes",
        structure=["common mistake", "personal result", "checklist promise"], format="founder_lessons",
        visual_hierarchy="Short lines, one idea each", educational_value="Concrete checklist",
        discussion_trigger="Invites readers to share their tool counts",
        why_it_may_have_resonated="Specific number contrast creates curiosity",
        reusable_template="Most {audience} {common mistake}. We {changed X} and {result}. Here's {artifact}.",
    )
    base.update(kw)
    return PostPattern(**base)


def test_copy_guard_detects_reused_wording():
    assert copied_ngrams(POST, _pattern()) == []
    copied = copied_ngrams(POST, _pattern(reusable_template="Most teams adding AI agents start with twenty tools {x}"))
    assert "most teams adding ai agents start" in copied


def test_swipe_analysis_accept_reject_and_summary(session, fake_llm):
    ok = SwipePost(text=POST, owner_reported_metrics={"reactions": 1200})
    bad = SwipePost(text=POST)
    session.add_all([ok, bad])
    session.flush()
    fake_llm.queue_parse("PostPattern", _pattern())
    fake_llm.queue_parse("PostPattern", _pattern(discussion_trigger="We cut ours to three and reliability went up"))
    analyze_swipe_post(session, ok, fake_llm, SKILLS)
    analyze_swipe_post(session, bad, fake_llm, SKILLS)
    assert ok.analysis_status == "analyzed" and ok.analysis["hook_type"] == "contrarian"
    assert bad.analysis_status == "rejected_copy" and bad.analysis["copied_phrases"]
    assert "<post>" in fake_llm.calls[0]["prompt"]

    summary = pattern_summary(session)
    assert summary["analyzed_posts"] == 1
    assert summary["hook_types"] == {"contrarian": 1} and summary["formats"] == {"founder_lessons": 1}
    assert "Not evidence" in summary["note"]
