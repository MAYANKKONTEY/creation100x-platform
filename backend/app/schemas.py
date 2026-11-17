"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl

from app.db import as_utc

# SQLite drops tzinfo; every timestamp the API returns is explicit UTC.
UTCDateTime = Annotated[datetime, AfterValidator(as_utc)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["rss", "hn_algolia", "github_search"]
    url: HttpUrl
    category: Literal["A", "B", "C", "D", "E"] = "A"
    enabled: bool = True
    max_items: int = Field(default=50, ge=1, le=200)


class SourcePatch(BaseModel):
    enabled: bool | None = None
    max_items: int | None = Field(default=None, ge=1, le=200)
    category: Literal["A", "B", "C", "D", "E"] | None = None


class SourceOut(ORM):
    id: int
    name: str
    kind: str
    url: str
    category: str
    enabled: bool
    max_items: int
    last_fetched_at: UTCDateTime | None
    last_error: str | None


class RawItemOut(ORM):
    id: int
    source_id: int
    url: str
    title: str
    summary: str | None
    published_at: UTCDateTime | None
    fetched_at: UTCDateTime
    category: str
    signals: dict
    triage_status: str
    triage: dict
    story_id: int | None


class OpportunityIn(BaseModel):
    raw_item_id: int | None = None
    title: str | None = None
    category: Literal["A", "B", "C", "D", "E"] | None = None


class SubScoresIn(BaseModel):
    """Judged sub-scores 0-10. Freshness is computed by the system and must not be supplied."""

    model_config = ConfigDict(extra="forbid")
    audience_relevance: float = Field(ge=0, le=10)
    business_importance: float = Field(ge=0, le=10)
    discussion_potential: float = Field(ge=0, le=10)
    virality_hypothesis: float = Field(ge=0, le=10)
    evidence_quality: float = Field(ge=0, le=10)


class OpportunityOut(ORM):
    id: int
    raw_item_id: int | None
    story_id: int | None
    title: str
    category: str
    pillar: str | None
    status: str
    sub_scores: dict
    score_total: float | None
    score_breakdown: dict
    scoring_version: str | None
    signals: dict
    analysis: dict
    created_at: UTCDateTime


class StoryOut(ORM):
    id: int
    key: str
    title: str
    category: str
    pillar: str | None
    first_seen_at: UTCDateTime
    last_seen_at: UTCDateTime
    latest_published_at: UTCDateTime | None


class RadarEntry(BaseModel):
    story: StoryOut
    opportunity: OpportunityOut | None
    coverage: dict


class StoryDetail(BaseModel):
    story: StoryOut
    opportunity: OpportunityOut | None
    items: list[RawItemOut]


class TriageRunIn(BaseModel):
    max_items: int | None = Field(default=None, ge=1, le=1000)


class PipelineRunIn(BaseModel):
    discover: bool = True


class SwipePostIn(BaseModel):
    text: str = Field(min_length=40, max_length=10000)
    author_name: str | None = Field(default=None, max_length=200)
    url: HttpUrl | None = None
    posted_at: datetime | None = None
    owner_note: str | None = Field(default=None, max_length=2000)
    owner_reported_metrics: dict[str, int] = Field(
        default_factory=dict, description="Only numbers you saw on LinkedIn, e.g. {'reactions': 1200}"
    )


class SwipePostOut(ORM):
    id: int
    text: str
    author_name: str | None
    url: str | None
    posted_at: UTCDateTime | None
    owner_note: str | None
    owner_reported_metrics: dict
    analysis_status: str
    analysis: dict
    created_at: UTCDateTime


class ResearchIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    opportunity_id: int | None = None
    recency_days: int = Field(default=30, ge=1, le=3650)


class EvidenceOut(ORM):
    url: str
    title: str | None
    page_age: str | None
    cited_texts: list


class ClaimOut(ORM):
    text: str
    claim_type: str
    source_urls: list
    status: str
    status_reason: str | None


class ResearchOut(ORM):
    id: int
    opportunity_id: int | None
    topic: str
    summary: str | None
    status: str
    model: str | None
    stats: dict
    created_at: UTCDateTime
    evidence: list[EvidenceOut]
    claims: list[ClaimOut]


class SafetyOut(BaseModel):
    can_publish: bool
    env_enabled: bool
    db_enabled: bool
    reason: str | None
    changed_at: str | None


class EmergencyStopIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class EnablePublishingIn(BaseModel):
    confirm: str
    reason: str = Field(min_length=3, max_length=500)


class WritingSampleIn(BaseModel):
    text: str = Field(min_length=50, max_length=20000)
    source: str | None = Field(default=None, max_length=200)


class WritingSampleOut(ORM):
    id: int
    text: str
    source: str | None
    created_at: UTCDateTime


class JobRunOut(ORM):
    id: int
    name: str
    status: str
    started_at: UTCDateTime
    finished_at: UTCDateTime | None
    stats: dict
    error: str | None


class LLMCallOut(ORM):
    id: int
    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None
    latency_ms: int
    est_cost_usd: float | None
    error: str | None
    created_at: UTCDateTime


class SkillOut(BaseModel):
    name: str
    description: str
    sections: list[str]
    references: list[str]
    problems: list[str]
