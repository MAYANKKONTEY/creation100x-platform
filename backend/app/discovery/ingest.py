"""Run connectors for enabled sources, de-duplicate by normalised URL, store RawItems.

One failing source never stops the others; its error is stored on the Source row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.discovery.base import normalize_url, url_hash
from app.models import RawItem, Source


@dataclass
class IngestStats:
    sources_ok: int = 0
    sources_failed: int = 0
    items_seen: int = 0
    items_new: int = 0
    errors: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def seed_sources(session: Session, path: Path) -> int:
    """Insert sources from YAML that don't exist yet (by name). Returns number added."""
    data = yaml.safe_load(path.read_text()) or {}
    existing = set(session.scalars(select(Source.name)))
    added = 0
    for spec in data.get("sources", []):
        if spec["name"] in existing:
            continue
        session.add(
            Source(
                name=spec["name"],
                kind=spec["kind"],
                url=spec["url"],
                category=spec.get("category", "A"),
                enabled=spec.get("enabled", True),
                max_items=spec.get("max_items", 50),
            )
        )
        added += 1
    session.flush()
    return added


def ingest(session: Session, connectors: dict[str, object], source_ids: list[int] | None = None) -> IngestStats:
    stats = IngestStats()
    query = select(Source).where(Source.enabled.is_(True))
    if source_ids:
        query = query.where(Source.id.in_(source_ids))
    sources = list(session.scalars(query.order_by(Source.id)))

    for source in sources:
        connector = connectors.get(source.kind)
        if connector is None:
            source.last_error = f"No connector for kind {source.kind!r}"
            stats.sources_failed += 1
            stats.errors[source.name] = source.last_error
            continue
        try:
            found = connector.fetch(source.url, source.max_items)
        except Exception as e:  # isolate per-source failures
            source.last_error = str(e)[:1000]
            source.last_fetched_at = utcnow()
            stats.sources_failed += 1
            stats.errors[source.name] = source.last_error
            continue

        stats.sources_ok += 1
        stats.items_seen += len(found)
        hashes = {url_hash(i.url): i for i in found}
        known = set(session.scalars(select(RawItem.url_hash).where(RawItem.url_hash.in_(list(hashes)))))
        for h, item in hashes.items():
            if h in known:
                continue
            session.add(
                RawItem(
                    source_id=source.id,
                    url=normalize_url(item.url),
                    url_hash=h,
                    title=item.title,
                    summary=item.summary,
                    author=item.author,
                    published_at=item.published_at,
                    category=source.category,
                    signals=item.signals,
                )
            )
            stats.items_new += 1
        source.last_error = None
        source.last_fetched_at = utcnow()
        session.flush()
    return stats
