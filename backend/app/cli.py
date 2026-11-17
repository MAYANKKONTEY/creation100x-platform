"""Command-line entry points.

    python -m app.cli seed-sources
    python -m app.cli discover
    python -m app.cli research "AI coding agents and junior developer hiring"
    python -m app.cli triage
    python -m app.cli pipeline            # discover -> triage -> select -> analyse (cron-friendly)
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.config import get_settings
from app.db import Database
from app.discovery.connectors import build_connectors
from app.discovery.ingest import ingest, seed_sources
from app.intelligence.config import load_pipeline_config
from app.intelligence.pipeline import run_pipeline
from app.intelligence.triage import TriageService
from app.jobs import run_job
from app.llm.base import LLMError
from app.llm.claude import build_claude_client
from app.llm.usage import UsageRecorder
from app.research.service import ResearchService
from app.scoring.models import load_scoring_config
from app.skills.loader import SkillLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="growthos")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-sources")
    sub.add_parser("discover")
    r = sub.add_parser("research")
    r.add_argument("topic")
    r.add_argument("--days", type=int, default=30)
    sub.add_parser("triage")
    p = sub.add_parser("pipeline")
    p.add_argument("--no-discover", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()
    github_token = settings.github_token.get_secret_value() if settings.github_token else None

    def http_client() -> httpx.Client:
        return httpx.Client(timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent})

    with db.session() as session:
        if args.cmd == "seed-sources":
            print(json.dumps({"added": seed_sources(session, settings.config_dir / "sources.yaml")}))
        elif args.cmd == "discover":
            with http_client() as http, run_job(session, "discovery") as job:
                stats = ingest(session, build_connectors(http, github_token=github_token))
                job.stats = stats.as_dict()
            print(json.dumps(stats.as_dict(), indent=2))
        elif args.cmd in ("triage", "pipeline"):
            recorder = UsageRecorder(session, settings.config_dir / "pricing.yaml")
            skills = SkillLoader(settings.skills_dir)
            pipeline_cfg = load_pipeline_config(settings.config_dir / "pipeline.yaml")
            scoring = load_scoring_config(settings.config_dir / "scoring.yaml")
            try:
                llm = build_claude_client(settings, on_usage=recorder)
            except LLMError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            if args.cmd == "triage":
                with run_job(session, "triage", recorder=recorder) as job:
                    out = TriageService(llm, skills, pipeline_cfg, scoring).run(session).as_dict()
                    job.stats = out
            else:
                with http_client() as http, run_job(session, "intelligence_pipeline", recorder=recorder) as job:
                    out = run_pipeline(session, build_connectors(http, github_token=github_token), llm, skills,
                                       pipeline_cfg, scoring, discover=not args.no_discover)
                    job.stats = out
            print(json.dumps(out, indent=2, default=str))
        elif args.cmd == "research":
            recorder = UsageRecorder(session, settings.config_dir / "pricing.yaml")
            try:
                llm = build_claude_client(settings, on_usage=recorder)
                with run_job(session, "research", recorder=recorder):
                    brief = ResearchService(llm, SkillLoader(settings.skills_dir)).run(session, args.topic, recency_days=args.days)
            except LLMError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(json.dumps({
                "brief_id": brief.id, "status": brief.status, "summary": brief.summary,
                "claims": [{"text": c.text, "status": c.status, "sources": c.source_urls} for c in brief.claims],
            }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
