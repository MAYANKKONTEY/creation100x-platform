from datetime import UTC, datetime, timedelta

import pytest

from app.config import REPO_ROOT
from app.scoring.models import ScoringConfigError, ScoringModel, load_scoring_config


@pytest.fixture(scope="module")
def cfg():
    return load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")


def test_config_has_three_models_matching_brief(cfg):
    assert set(cfg.models) == {"content_opportunity", "post_quality", "visual_quality"}
    assert cfg.get("content_opportunity").weights == {
        "audience_relevance": 0.20, "freshness": 0.15, "business_importance": 0.20,
        "discussion_potential": 0.15, "virality_hypothesis": 0.20, "evidence_quality": 0.10,
    }
    assert cfg.get("post_quality").weights["hook_quality"] == 0.20
    assert cfg.get("visual_quality").weights["brand_consistency"] == 0.10


def test_weights_must_sum_to_one():
    with pytest.raises(ScoringConfigError):
        ScoringModel("bad", "1", {"a": 0.5, "b": 0.4})


def test_weight_range_validated():
    with pytest.raises(ScoringConfigError):
        ScoringModel("bad", "1", {"a": 1.5, "b": -0.5})


def test_score_maths_and_breakdown(cfg):
    model = cfg.get("post_quality")
    res = model.score({"hook_quality": 8, "information_value": 7, "audience_relevance": 9,
                       "originality": 6, "readability": 10, "credibility": 5})
    # 8*2 + 7*2 + 9*2 + 6*1.5 + 10*1 + 5*1.5 = 16+14+18+9+10+7.5
    assert res.total == 74.5
    assert res.passes_threshold is True
    assert res.breakdown["originality"] == {"raw": 6.0, "weight": 0.15, "contribution": 9.0}
    assert "Not a prediction" in res.disclaimer
    assert res.version == model.version


def test_score_rejects_missing_unknown_and_out_of_range(cfg):
    model = cfg.get("visual_quality")
    full = dict.fromkeys(model.weights, 5)
    with pytest.raises(ValueError, match="missing"):
        model.score({k: v for k, v in full.items() if k != "originality"})
    with pytest.raises(ValueError, match="unknown"):
        model.score({**full, "virality": 9})
    with pytest.raises(ValueError, match="outside"):
        model.score({**full, "originality": 11})


def test_freshness_decay(cfg):
    now = datetime(2026, 11, 17, 12, tzinfo=UTC)
    assert cfg.freshness(now, now) == 10.0
    assert cfg.freshness(now - timedelta(hours=48), now) == 5.0
    assert cfg.freshness(now - timedelta(hours=96), now) == 2.5
    assert cfg.freshness(None, now) == 3.0
    # naive datetimes (as returned by SQLite) are treated as UTC
    assert cfg.freshness(datetime(2026, 11, 17, 12), now) == 10.0
    # future dates clamp to 10
    assert cfg.freshness(now + timedelta(hours=5), now) == 10.0
