"""FastAPI application factory and Milestone 1 routes."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings, get_settings
from app.db import Database
from app.discovery.connectors import build_connectors
from app.discovery.ingest import ingest, seed_sources
from app.jobs import run_job
from app.llm.base import LLMClient, LLMError, LLMNotConfigured, LLMRefusal
from app.llm.claude import build_claude_client
from app.llm.usage import UsageRecorder
from app.models import JobRun, LLMCall, Opportunity, RawItem, ResearchBrief, Source, WritingSample
from app.research.service import ResearchService
from app.safety import killswitch
from app.scoring.models import load_scoring_config
from app.scoring.opportunity import score_opportunity
from app.skills.loader import SkillLoader, validate_skill

LLMFactory = Callable[[Settings, UsageRecorder], LLMClient]


def default_llm_factory(settings: Settings, recorder: UsageRecorder) -> LLMClient:
    return build_claude_client(settings, on_usage=recorder)


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    llm_factory: LLMFactory = default_llm_factory,
    http_client: httpx.Client | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_all()
        owns_http = http_client is None
        app.state.http = http_client or httpx.Client(
            timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}
        )
        yield
        if owns_http:
            app.state.http.close()

    app = FastAPI(title="LinkedIn Growth OS", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.llm_factory = llm_factory
    app.state.skills = SkillLoader(settings.skills_dir)
    app.state.scoring = load_scoring_config(settings.config_dir / "scoring.yaml")

    def get_session(request: Request) -> Iterator[Session]:
        with request.app.state.db.session() as s:
            yield s

    SessionDep = Depends(get_session)

    def make_llm(request: Request, session: Session) -> tuple[LLMClient, UsageRecorder]:
        recorder = UsageRecorder(session, settings.config_dir / "pricing.yaml")
        try:
            return request.app.state.llm_factory(settings, recorder), recorder
        except LLMNotConfigured as e:
            raise HTTPException(503, f"LLM not configured: {e}") from e

    # ------------------------------------------------------------------ health
    @app.get("/api/health")
    def health(session: Session = SessionDep):
        session.execute(text("SELECT 1"))
        state = killswitch.get_state(session, settings.publishing_enabled)
        return {
            "status": "ok",
            "env": settings.app_env,
            "database": "ok",
            "llm_configured": settings.llm_configured,
            "publishing_can_publish": state.can_publish,
            "skills": len(app.state.skills.names()),
        }

    # ----------------------------------------------------------------- sources
    @app.get("/api/sources", response_model=list[schemas.SourceOut])
    def list_sources(session: Session = SessionDep):
        return session.scalars(select(Source).order_by(Source.id)).all()

    @app.post("/api/sources", response_model=schemas.SourceOut, status_code=201)
    def create_source(body: schemas.SourceIn, session: Session = SessionDep):
        src = Source(**{**body.model_dump(), "url": str(body.url)})
        session.add(src)
        try:
            session.flush()
        except IntegrityError as e:
            raise HTTPException(409, "A source with this name already exists") from e
        return src

    @app.patch("/api/sources/{source_id}", response_model=schemas.SourceOut)
    def patch_source(source_id: int, body: schemas.SourcePatch, session: Session = SessionDep):
        src = session.get(Source, source_id)
        if not src:
            raise HTTPException(404, "Source not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(src, k, v)
        session.flush()
        return src

    @app.post("/api/sources/seed")
    def seed(session: Session = SessionDep):
        return {"added": seed_sources(session, settings.config_dir / "sources.yaml")}

    # --------------------------------------------------------------- discovery
    @app.post("/api/discovery/run")
    def run_discovery(request: Request, source_ids: list[int] | None = None, session: Session = SessionDep):
        with run_job(session, "discovery") as job:
            stats = ingest(session, build_connectors(request.app.state.http), source_ids)
            job.stats = stats.as_dict()
        return {"job_id": job.id, **stats.as_dict()}

    @app.get("/api/items", response_model=list[schemas.RawItemOut])
    def list_items(
        session: Session = SessionDep,
        category: str | None = Query(default=None, pattern="^[A-E]$"),
        since: datetime | None = None,
        q: str | None = Query(default=None, max_length=200),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        stmt = select(RawItem)
        if category:
            stmt = stmt.where(RawItem.category == category)
        if since:
            stmt = stmt.where(RawItem.published_at >= since)
        if q:
            stmt = stmt.where(RawItem.title.ilike(f"%{q}%"))
        return session.scalars(stmt.order_by(RawItem.published_at.desc().nullslast(), RawItem.id.desc()).limit(limit)).all()

    # ----------------------------------------------------------- opportunities
    @app.post("/api/opportunities", response_model=schemas.OpportunityOut, status_code=201)
    def create_opportunity(body: schemas.OpportunityIn, session: Session = SessionDep):
        item = session.get(RawItem, body.raw_item_id) if body.raw_item_id else None
        if body.raw_item_id and not item:
            raise HTTPException(404, "Raw item not found")
        title = body.title or (item.title if item else None)
        category = body.category or (item.category if item else None)
        if not title or not category:
            raise HTTPException(422, "title and category are required when no raw_item_id is given")
        opp = Opportunity(raw_item_id=body.raw_item_id, title=title, category=category)
        session.add(opp)
        session.flush()
        return opp

    @app.post("/api/opportunities/{opp_id}/score", response_model=schemas.OpportunityOut)
    def score(opp_id: int, body: schemas.SubScoresIn, session: Session = SessionDep):
        opp = session.get(Opportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        return score_opportunity(session, opp, body.model_dump(), app.state.scoring)

    @app.get("/api/opportunities", response_model=list[schemas.OpportunityOut])
    def list_opportunities(
        session: Session = SessionDep,
        category: str | None = Query(default=None, pattern="^[A-E]$"),
        min_score: float | None = Query(default=None, ge=0, le=100),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        stmt = select(Opportunity)
        if category:
            stmt = stmt.where(Opportunity.category == category)
        if min_score is not None:
            stmt = stmt.where(Opportunity.score_total >= min_score)
        return session.scalars(stmt.order_by(Opportunity.score_total.desc().nullslast(), Opportunity.id.desc()).limit(limit)).all()

    @app.get("/api/scoring/models")
    def scoring_models():
        cfg = app.state.scoring
        return {
            "disclaimer": "Heuristic ranking scores, not probabilities of reach.",
            "freshness": {"half_life_hours": cfg.freshness_half_life_hours, "unknown_date_score": cfg.unknown_date_score},
            "models": {n: {"version": m.version, "weights": m.weights, "threshold": m.threshold} for n, m in cfg.models.items()},
        }

    # ---------------------------------------------------------------- research
    @app.post("/api/research", response_model=schemas.ResearchOut, status_code=201)
    def research(body: schemas.ResearchIn, request: Request, session: Session = SessionDep):
        if body.opportunity_id and not session.get(Opportunity, body.opportunity_id):
            raise HTTPException(404, "Opportunity not found")
        llm, recorder = make_llm(request, session)
        service = ResearchService(llm, app.state.skills)
        try:
            with run_job(session, "research", recorder=recorder) as job:
                brief = service.run(session, body.topic, body.opportunity_id, body.recency_days)
                job.stats = {"brief_id": brief.id, **brief.stats}
        except LLMRefusal as e:
            raise HTTPException(422, f"Model declined this topic ({e.category}). Sent to review.") from e
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        return brief

    @app.get("/api/research/{brief_id}", response_model=schemas.ResearchOut)
    def get_research(brief_id: int, session: Session = SessionDep):
        brief = session.get(ResearchBrief, brief_id)
        if not brief:
            raise HTTPException(404, "Research brief not found")
        return brief

    @app.get("/api/research", response_model=list[schemas.ResearchOut])
    def list_research(session: Session = SessionDep, limit: int = Query(default=20, ge=1, le=200)):
        return session.scalars(select(ResearchBrief).order_by(ResearchBrief.id.desc()).limit(limit)).all()

    # ------------------------------------------------------------------ safety
    def _safety(session: Session) -> schemas.SafetyOut:
        st = killswitch.get_state(session, settings.publishing_enabled)
        return schemas.SafetyOut(can_publish=st.can_publish, env_enabled=st.env_enabled, db_enabled=st.db_enabled,
                                 reason=st.reason, changed_at=st.changed_at)

    @app.get("/api/safety", response_model=schemas.SafetyOut)
    def safety(session: Session = SessionDep):
        return _safety(session)

    @app.post("/api/safety/emergency-stop", response_model=schemas.SafetyOut)
    def emergency_stop(body: schemas.EmergencyStopIn, session: Session = SessionDep):
        killswitch.emergency_stop(session, body.reason)
        return _safety(session)

    @app.post("/api/safety/enable-publishing", response_model=schemas.SafetyOut)
    def enable_publishing(body: schemas.EnablePublishingIn, session: Session = SessionDep):
        try:
            killswitch.enable_publishing(session, body.confirm, body.reason)
        except PermissionError as e:
            raise HTTPException(400, str(e)) from e
        return _safety(session)

    # ------------------------------------------------------------- brand voice
    @app.post("/api/brand-voice/samples", response_model=schemas.WritingSampleOut, status_code=201)
    def add_sample(body: schemas.WritingSampleIn, session: Session = SessionDep):
        sample = WritingSample(text=body.text, source=body.source)
        session.add(sample)
        session.flush()
        return sample

    @app.get("/api/brand-voice/samples", response_model=list[schemas.WritingSampleOut])
    def list_samples(session: Session = SessionDep):
        return session.scalars(select(WritingSample).order_by(WritingSample.id)).all()

    # -------------------------------------------------------------- logs/skills
    @app.get("/api/jobs", response_model=list[schemas.JobRunOut])
    def list_jobs(session: Session = SessionDep, limit: int = Query(default=50, ge=1, le=500)):
        return session.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(limit)).all()

    @app.get("/api/llm-calls", response_model=list[schemas.LLMCallOut])
    def list_llm_calls(session: Session = SessionDep, limit: int = Query(default=50, ge=1, le=500)):
        return session.scalars(select(LLMCall).order_by(LLMCall.id.desc()).limit(limit)).all()

    @app.get("/api/skills", response_model=list[schemas.SkillOut])
    def list_skills():
        return [
            schemas.SkillOut(name=s.name, description=s.description, sections=s.sections,
                             references=s.references(), problems=validate_skill(s))
            for s in app.state.skills.all()
        ]

    return app
