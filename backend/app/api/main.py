"""FastAPI application factory and Milestone 1 routes."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings, get_settings
from app.db import Database, utcnow
from app.discovery.connectors import build_connectors
from app.discovery.ingest import ingest, seed_sources
from app.intelligence.analysis import AnalysisService
from app.intelligence.clustering import story_coverage
from app.intelligence.config import load_pipeline_config
from app.intelligence.pipeline import run_pipeline
from app.intelligence.swipe import analyze_swipe_post, pattern_summary
from app.intelligence.triage import TriageService
from app.jobs import run_job
from app.llm.base import LLMClient, LLMError, LLMNotConfigured, LLMRefusal
from app.llm.claude import build_claude_client
from app.llm.usage import UsageRecorder
from app.models import (
    JobRun,
    LLMCall,
    Opportunity,
    RawItem,
    ResearchBrief,
    Source,
    Story,
    SwipePost,
    WritingSample,
)
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
    app.state.pipeline = load_pipeline_config(settings.config_dir / "pipeline.yaml")
    github_token = settings.github_token.get_secret_value() if settings.github_token else None

    def connectors(request: Request) -> dict:
        return build_connectors(request.app.state.http, github_token=github_token)

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
            stats = ingest(session, connectors(request), source_ids)
            job.stats = stats.as_dict()
        return {"job_id": job.id, **stats.as_dict()}

    @app.get("/api/items", response_model=list[schemas.RawItemOut])
    def list_items(
        session: Session = SessionDep,
        category: str | None = Query(default=None, pattern="^[A-E]$"),
        since: datetime | None = None,
        q: str | None = Query(default=None, max_length=200),
        triage_status: str | None = Query(default=None, pattern="^(pending|relevant|irrelevant|stale|error)$"),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        stmt = select(RawItem)
        if category:
            stmt = stmt.where(RawItem.category == category)
        if triage_status:
            stmt = stmt.where(RawItem.triage_status == triage_status)
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
        pillar: str | None = Query(default=None, max_length=40),
        status: str | None = Query(default=None, max_length=30),
        min_score: float | None = Query(default=None, ge=0, le=100),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        stmt = select(Opportunity)
        if category:
            stmt = stmt.where(Opportunity.category == category)
        if pillar:
            stmt = stmt.where(Opportunity.pillar == pillar)
        if status:
            stmt = stmt.where(Opportunity.status == status)
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

    # ------------------------------------------------------------ intelligence
    @app.post("/api/triage/run")
    def run_triage(request: Request, body: schemas.TriageRunIn | None = None, session: Session = SessionDep):
        cfg = app.state.pipeline
        if body and body.max_items:
            cfg = cfg.model_copy(update={"triage": cfg.triage.model_copy(update={"max_items_per_run": body.max_items})})
        llm, recorder = make_llm(request, session)
        with run_job(session, "triage", recorder=recorder) as job:
            stats = TriageService(llm, app.state.skills, cfg, app.state.scoring).run(session)
            job.stats = stats.as_dict()
        return {"job_id": job.id, **stats.as_dict()}

    @app.post("/api/opportunities/{opp_id}/analyze", response_model=schemas.OpportunityOut)
    def analyze_opportunity(opp_id: int, request: Request, session: Session = SessionDep):
        opp = session.get(Opportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        llm, recorder = make_llm(request, session)
        try:
            with run_job(session, "opportunity.analyze", recorder=recorder) as job:
                AnalysisService(llm, app.state.skills, app.state.pipeline).analyze(session, opp)
                job.stats = {"opportunity_id": opp.id, "status": opp.status}
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        return session.get(Opportunity, opp_id)

    @app.post("/api/pipeline/run")
    def pipeline_run(request: Request, body: schemas.PipelineRunIn | None = None, session: Session = SessionDep):
        llm, recorder = make_llm(request, session)
        with run_job(session, "intelligence_pipeline", recorder=recorder) as job:
            out = run_pipeline(session, connectors(request), llm, app.state.skills, app.state.pipeline,
                               app.state.scoring, discover=body.discover if body else True)
            job.stats = out
        return {"job_id": job.id, **out}

    def _radar(session: Session, categories: tuple[str, ...], days: int, pillar: str | None, limit: int):
        since = utcnow() - timedelta(days=days)
        stmt = (
            select(Story, Opportunity)
            .outerjoin(Opportunity, Opportunity.story_id == Story.id)
            .where(Story.category.in_(categories), Story.last_seen_at >= since)
        )
        if pillar:
            stmt = stmt.where(Story.pillar == pillar)
        rows = session.execute(stmt.order_by(Opportunity.score_total.desc().nullslast(), Story.id.desc()).limit(limit)).all()
        return [
            schemas.RadarEntry(
                story=schemas.StoryOut.model_validate(story),
                opportunity=schemas.OpportunityOut.model_validate(opp) if opp else None,
                coverage=story_coverage(session, story.id),
            )
            for story, opp in rows
        ]

    @app.get("/api/radar/trends", response_model=list[schemas.RadarEntry])
    def ai_trend_radar(session: Session = SessionDep, days: int = Query(default=7, ge=1, le=90),
                       pillar: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
        return _radar(session, ("A",), days, pillar, limit)

    @app.get("/api/radar/business", response_model=list[schemas.RadarEntry])
    def business_radar(session: Session = SessionDep, days: int = Query(default=7, ge=1, le=90),
                       pillar: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
        return _radar(session, ("B", "C", "D"), days, pillar, limit)

    @app.get("/api/stories/{story_id}", response_model=schemas.StoryDetail)
    def story_detail(story_id: int, session: Session = SessionDep):
        story = session.get(Story, story_id)
        if not story:
            raise HTTPException(404, "Story not found")
        opp = session.scalar(select(Opportunity).where(Opportunity.story_id == story_id))
        return schemas.StoryDetail(
            story=schemas.StoryOut.model_validate(story),
            opportunity=schemas.OpportunityOut.model_validate(opp) if opp else None,
            items=[schemas.RawItemOut.model_validate(i) for i in story.items],
        )

    # -------------------------------------------------------------- swipe file
    @app.post("/api/swipe-file", response_model=schemas.SwipePostOut, status_code=201)
    def add_swipe_post(body: schemas.SwipePostIn, session: Session = SessionDep):
        post = SwipePost(**{**body.model_dump(), "url": str(body.url) if body.url else None})
        session.add(post)
        session.flush()
        return post

    @app.get("/api/swipe-file", response_model=list[schemas.SwipePostOut])
    def list_swipe_posts(session: Session = SessionDep, limit: int = Query(default=100, ge=1, le=500)):
        return session.scalars(select(SwipePost).order_by(SwipePost.id.desc()).limit(limit)).all()

    @app.post("/api/swipe-file/{post_id}/analyze", response_model=schemas.SwipePostOut)
    def analyze_swipe(post_id: int, request: Request, session: Session = SessionDep):
        post = session.get(SwipePost, post_id)
        if not post:
            raise HTTPException(404, "Swipe post not found")
        llm, recorder = make_llm(request, session)
        try:
            with run_job(session, "swipe.analyze", recorder=recorder):
                analyze_swipe_post(session, post, llm, app.state.skills)
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        return session.get(SwipePost, post_id)

    @app.get("/api/patterns")
    def patterns(session: Session = SessionDep):
        return pattern_summary(session)

    @app.get("/api/pipeline/config")
    def pipeline_config():
        return app.state.pipeline.model_dump()

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
