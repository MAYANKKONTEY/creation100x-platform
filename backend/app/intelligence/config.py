"""Typed loader for config/pipeline.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class TriageConfig(BaseModel):
    batch_size: int = Field(default=15, ge=1, le=50)
    max_items_per_run: int = Field(default=150, ge=1)
    max_age_hours: float = Field(default=96, gt=0)
    effort: str = "low"
    min_audience_relevance: float = Field(default=5, ge=0, le=10)


class ClusteringConfig(BaseModel):
    window_hours: float = Field(default=168, gt=0)
    title_jaccard_threshold: float = Field(default=0.6, gt=0, le=1)


class SelectionConfig(BaseModel):
    top_n: int = Field(default=5, ge=1)
    max_per_pillar: int = Field(default=2, ge=1)


class AnalysisConfig(BaseModel):
    effort: str = "medium"


class PipelineConfig(BaseModel):
    audience: str
    pillars: list[str] = Field(min_length=1)
    triage: TriageConfig = TriageConfig()
    clustering: ClusteringConfig = ClusteringConfig()
    selection: SelectionConfig = SelectionConfig()
    analysis: AnalysisConfig = AnalysisConfig()


def load_pipeline_config(path: Path) -> PipelineConfig:
    return PipelineConfig.model_validate(yaml.safe_load(path.read_text()) or {})
