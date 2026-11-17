"""Apply the Content Opportunity Score to an Opportunity. Freshness is always computed, never supplied."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Opportunity, RawItem
from app.scoring.models import ScoringConfig

MODEL = "content_opportunity"
LLM_DIMENSIONS = ("audience_relevance", "business_importance", "discussion_potential", "virality_hypothesis", "evidence_quality")


def score_opportunity(session: Session, opp: Opportunity, judged: dict[str, float], config: ScoringConfig) -> Opportunity:
    if "freshness" in judged:
        raise ValueError("freshness is computed from the item date and cannot be supplied")
    item = session.get(RawItem, opp.raw_item_id) if opp.raw_item_id else None
    sub = {**judged, "freshness": config.freshness(item.published_at if item else None)}
    result = config.get(MODEL).score(sub)
    opp.sub_scores = sub
    opp.score_total = result.total
    opp.score_breakdown = result.as_dict()
    opp.scoring_version = result.version
    opp.status = "scored"
    session.flush()
    return opp
