"""Configurable weighted scoring models.

These are heuristics for ranking candidates. They are not probabilities of reach or virality,
and every result says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from app.db import as_utc, utcnow

DISCLAIMER = "Heuristic ranking score (0-100). Not a prediction or probability of reach."
WEIGHT_TOLERANCE = 1e-6


class ScoringConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreResult:
    model: str
    version: str
    total: float
    breakdown: dict[str, dict[str, float]]
    disclaimer: str = DISCLAIMER
    passes_threshold: bool | None = None

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "version": self.version,
            "total": self.total,
            "breakdown": self.breakdown,
            "disclaimer": self.disclaimer,
            "passes_threshold": self.passes_threshold,
        }


@dataclass(frozen=True)
class ScoringModel:
    name: str
    version: str
    weights: dict[str, float]
    threshold: float | None = None

    def __post_init__(self) -> None:
        if not self.weights:
            raise ScoringConfigError(f"{self.name}: no weights")
        for k, w in self.weights.items():
            if not 0 <= w <= 1:
                raise ScoringConfigError(f"{self.name}: weight {k}={w} outside [0, 1]")
        total = sum(self.weights.values())
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            raise ScoringConfigError(f"{self.name}: weights sum to {total:.4f}, expected 1.0")

    def score(self, sub_scores: dict[str, float]) -> ScoreResult:
        missing = set(self.weights) - set(sub_scores)
        if missing:
            raise ValueError(f"{self.name}: missing sub-scores {sorted(missing)}")
        unknown = set(sub_scores) - set(self.weights)
        if unknown:
            raise ValueError(f"{self.name}: unknown sub-scores {sorted(unknown)}")
        breakdown: dict[str, dict[str, float]] = {}
        total = 0.0
        for dim, weight in self.weights.items():
            raw = float(sub_scores[dim])
            if not 0 <= raw <= 10 or math.isnan(raw):
                raise ValueError(f"{self.name}: {dim}={raw} outside [0, 10]")
            contribution = raw * 10 * weight
            breakdown[dim] = {"raw": raw, "weight": weight, "contribution": round(contribution, 2)}
            total += contribution
        total = round(total, 2)
        passes = None if self.threshold is None else total >= self.threshold
        return ScoreResult(self.name, self.version, total, breakdown, passes_threshold=passes)


@dataclass
class ScoringConfig:
    models: dict[str, ScoringModel]
    freshness_half_life_hours: float = 48.0
    unknown_date_score: float = 3.0
    extra: dict = field(default_factory=dict)

    def get(self, name: str) -> ScoringModel:
        try:
            return self.models[name]
        except KeyError as e:
            raise ScoringConfigError(f"Unknown scoring model {name!r}") from e

    def freshness(self, published_at: datetime | None, now: datetime | None = None) -> float:
        """Deterministic exponential decay: 10 at publish time, 5 after one half-life."""
        if published_at is None:
            return self.unknown_date_score
        now = as_utc(now) or utcnow()
        age_h = max(0.0, (now - as_utc(published_at)).total_seconds() / 3600)
        return round(10 * 0.5 ** (age_h / self.freshness_half_life_hours), 2)


def load_scoring_config(path: Path) -> ScoringConfig:
    data = yaml.safe_load(path.read_text()) or {}
    models: dict[str, ScoringModel] = {}
    for name, spec in (data.get("models") or {}).items():
        models[name] = ScoringModel(
            name=name,
            version=str(spec.get("version", "unversioned")),
            weights={k: float(v) for k, v in (spec.get("weights") or {}).items()},
            threshold=spec.get("auto_publish_min"),
        )
    fresh = data.get("freshness") or {}
    return ScoringConfig(
        models=models,
        freshness_half_life_hours=float(fresh.get("half_life_hours", 48)),
        unknown_date_score=float(fresh.get("unknown_date_score", 3.0)),
    )
