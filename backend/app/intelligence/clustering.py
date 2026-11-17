"""Merge items about the same real-world story.

Two layers:
1. Claude assigns a short `story_key` during triage and is shown recent keys so it can reuse them
   (catches different headlines for the same event).
2. A deterministic title-similarity backstop (Jaccard on content words) catches near-identical
   headlines even when the model invents a new key.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import as_utc, utcnow
from app.models import RawItem, Story

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by", "from", "is", "are",
    "was", "its", "it", "as", "how", "why", "what", "new", "now", "this", "that", "your", "you", "s",
    "show", "hn", "ask",
}


def slugify_key(value: str, limit: int = 80) -> str:
    slug = "-".join(_WORD.findall(value.lower()))
    return slug[:limit].strip("-") or "story"


def title_tokens(title: str) -> set[str]:
    return {w for w in _WORD.findall(title.lower()) if w not in _STOP and len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def recent_stories(session: Session, window_hours: float, now: datetime | None = None) -> list[Story]:
    since = (as_utc(now) or utcnow()) - timedelta(hours=window_hours)
    return list(session.scalars(select(Story).where(Story.last_seen_at >= since).order_by(Story.last_seen_at.desc())))


def find_story(
    session: Session, key: str, title: str, window_hours: float, threshold: float, now: datetime | None = None
) -> Story | None:
    """Exact key match first (any age within window), then title-similarity backstop."""
    candidates = recent_stories(session, window_hours, now)
    for story in candidates:
        if story.key == key:
            return story
    tokens = title_tokens(title)
    best, best_score = None, 0.0
    for story in candidates:
        score = jaccard(tokens, title_tokens(story.title))
        if score > best_score:
            best, best_score = story, score
    return best if best_score >= threshold else None


def attach_to_story(
    session: Session, item: RawItem, key: str, category: str, pillar: str, window_hours: float, threshold: float
) -> tuple[Story, bool]:
    """Attach an item to an existing story or create one. Returns (story, created)."""
    key = slugify_key(key)
    story = find_story(session, key, item.title, window_hours, threshold)
    created = story is None
    if created:
        # A key collision with an old story outside the window: make the new key unique.
        unique_key, n = key, 2
        while session.scalar(select(Story.id).where(Story.key == unique_key)) is not None:
            unique_key, n = f"{key}-{n}", n + 1
        story = Story(key=unique_key, title=item.title, category=category, pillar=pillar)
        session.add(story)
        session.flush()
    item.story_id = story.id
    story.last_seen_at = utcnow()
    published = as_utc(item.published_at)
    if published and (story.latest_published_at is None or published > as_utc(story.latest_published_at)):
        story.latest_published_at = published
    session.flush()
    return story, created


def story_coverage(session: Session, story_id: int) -> dict:
    """Real, countable signals: how many items and distinct sources cover this story."""
    rows = session.execute(select(RawItem.source_id, RawItem.signals).where(RawItem.story_id == story_id)).all()
    return {"items": len(rows), "distinct_sources": len({r.source_id for r in rows})}
