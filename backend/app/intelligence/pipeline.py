"""Daily intelligence pipeline: discover -> triage -> select (pillar-balanced) -> analyse.

Runs from the API, the CLI (`python -m app.cli pipeline`) or cron until the M7 scheduler exists.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.ingest import ingest
from app.intelligence.analysis import AnalysisService
from app.intelligence.config import PipelineConfig
from app.intelligence.triage import TriageService
from app.llm.base import LLMClient
from app.models import Opportunity
from app.scoring.models import ScoringConfig
from app.skills.loader import SkillLoader

OPEN_STATUSES = ("scored", "analyzed")


def candidate_opportunities(session: Session, limit: int = 200) -> list[Opportunity]:
    return list(
        session.scalars(
            select(Opportunity)
            .where(Opportunity.status.in_(OPEN_STATUSES), Opportunity.score_total.is_not(None))
            .order_by(Opportunity.score_total.desc())
            .limit(limit)
        )
    )


def run_pipeline(
    session: Session,
    connectors: dict,
    llm: LLMClient,
    skills: SkillLoader,
    pipeline: PipelineConfig,
    scoring: ScoringConfig,
    discover: bool = True,
) -> dict:
    out: dict = {}
    if discover:
        out["discovery"] = ingest(session, connectors).as_dict()
    triage = TriageService(llm, skills, pipeline, scoring).run(session)
    out["triage"] = triage.as_dict()
    picked, analysis = AnalysisService(llm, skills, pipeline).analyze_selected(session, candidate_opportunities(session))
    out["analysis"] = analysis.as_dict()
    out["selected_opportunity_ids"] = [o.id for o in picked]
    return out
