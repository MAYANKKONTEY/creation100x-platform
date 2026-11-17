"""Command-line entry points.

    python -m app.cli seed-sources
    python -m app.cli discover
    python -m app.cli research "AI coding agents and junior developer hiring"
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
from app.jobs import run_job
from app.llm.base import LLMError
from app.llm.claude import build_claude_client
from app.llm.usage import UsageRecorder
from app.research.service import ResearchService
from app.skills.loader import SkillLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="growthos")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-sources")
    sub.add_parser("discover")
    r = sub.add_parser("research")
    r.add_argument("topic")
    r.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)

    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()

    with db.session() as session:
        if args.cmd == "seed-sources":
            print(json.dumps({"added": seed_sources(session, settings.config_dir / "sources.yaml")}))
        elif args.cmd == "discover":
            with httpx.Client(timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}) as http:
                with run_job(session, "discovery") as job:
                    stats = ingest(session, build_connectors(http))
                    job.stats = stats.as_dict()
            print(json.dumps(stats.as_dict(), indent=2))
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
