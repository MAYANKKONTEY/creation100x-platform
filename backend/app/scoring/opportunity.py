"""Apply the Content Opportunity Score to an Opportunity. Freshness is always computed, never supplied."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Opportunity, RawItem, Story
from app.scoring.models import ScoringConfig

MODEL = "content_opportunity"
LLM_DIMENSIONS = ("audience_relevance", "business_importance", "discussion_potential", "virality_hypothesis", "evidence_quality")


def score_opportunity(session: Session, opp: Opportunity, judged: dict[str, float], config: ScoringConfig) -> Opportunity:
    if "freshness" in judged:
        raise ValueError("freshness is computed from the item date and cannot be supplied")
    # Freshness follows the newest development of the story, else the source item's date.
    published_at = None
    if opp.story_id and (story := session.get(Story, opp.story_id)):
        published_at = story.latest_published_at
    elif opp.raw_item_id and (item := session.get(RawItem, opp.raw_item_id)):
        published_at = item.published_at
    sub = {**judged, "freshness": config.freshness(published_at)}
    result = config.get(MODEL).score(sub)
    opp.sub_scores = sub
    opp.score_total = result.total
    opp.score_breakdown = result.as_dict()
    opp.scoring_version = result.version
    if opp.status == "new":  # never move an analysed/researched opportunity backwards
        opp.status = "scored"
    session.flush()
    return opp
