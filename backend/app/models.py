"""ORM models for Milestone 1. Later milestones add hooks, drafts, visuals, publishing, metrics."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow


class Category(StrEnum):
    AI_TECH = "A"
    BUSINESS = "B"
    BUSINESS_PROBLEMS = "C"
    STARTUP_OPPORTUNITIES = "D"
    LINKEDIN_CONTENT = "E"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    SOURCED = "sourced"
    UNSUPPORTED = "unsupported"


class TriageStatus(StrEnum):
    PENDING = "pending"
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    STALE = "stale"
    ERROR = "error"


class JobStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(2), default=Category.AI_TECH)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_items: Mapped[int] = mapped_column(Integer, default=50)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list[RawItem]] = relationship(back_populates="source")


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    category: Mapped[str] = mapped_column(String(2))
    # Only metrics the source itself provides (e.g. HN points). Never estimated.
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    triage_status: Mapped[str] = mapped_column(String(20), default=TriageStatus.PENDING, index=True)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {category, pillar, sub_scores, reasons, story_key, model} from the triage stage
    triage: Mapped[dict] = mapped_column(JSON, default=dict)
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)

    source: Mapped[Source] = relationship(back_populates="items")
    story: Mapped[Story | None] = relationship(back_populates="items")


class Story(Base):
    """One real-world story, possibly covered by several items from different sources."""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(2))
    pillar: Mapped[str | None] = mapped_column(String(40), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    latest_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list[RawItem]] = relationship(back_populates="story")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_item_id: Mapped[int | None] = mapped_column(ForeignKey("raw_items.id", ondelete="SET NULL"))
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), unique=True)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(2))
    pillar: Mapped[str | None] = mapped_column(String(40), index=True)
    # new -> scored -> analyzed | needs_review -> researched ...
    status: Mapped[str] = mapped_column(String(30), default="new")
    sub_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    score_total: Mapped[float | None] = mapped_column(Float, index=True)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_version: Mapped[str | None] = mapped_column(String(40))
    # Real, countable signals only: coverage (items, distinct sources) and source-provided metrics.
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchBrief(Base):
    __tablename__ = "research_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    topic: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="complete")
    model: Mapped[str | None] = mapped_column(String(80))
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    evidence: Mapped[list[Evidence]] = relationship(back_populates="brief", cascade="all, delete-orphan")
    claims: Mapped[list[Claim]] = relationship(back_populates="brief", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("research_briefs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    page_age: Mapped[str | None] = mapped_column(String(80))
    cited_texts: Mapped[list] = mapped_column(JSON, default=list)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    brief: Mapped[ResearchBrief] = relationship(back_populates="evidence")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("research_briefs.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(20))
    source_urls: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20))
    status_reason: Mapped[str | None] = mapped_column(Text)

    brief: Mapped[ResearchBrief] = relationship(back_populates="claims")


class WritingSample(Base):
    __tablename__ = "writing_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))  # e.g. "linkedin post 2026-05"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SwipePost(Base):
    """A public LinkedIn post the owner pasted in for pattern analysis (no scraping)."""

    __tablename__ = "swipe_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_note: Mapped[str | None] = mapped_column(Text)
    # Numbers the owner typed in from what LinkedIn showed. Labelled owner-reported; never estimated.
    owner_reported_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    stop_reason: Mapped[str | None] = mapped_column(String(40))
    request_id: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
