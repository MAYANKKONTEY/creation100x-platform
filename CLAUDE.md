# LinkedIn Growth OS

Single-user LinkedIn content system. Read `ARCHITECTURE.md` for design and `TASKS.md` for status.

- Content work (posts, hooks, visuals, SEO, analytics): use the skills in `.claude/skills/`. See `SKILLS_INDEX.md`.
- Backend: `backend/` (FastAPI, SQLAlchemy 2.0, Anthropic SDK). Run tests with `cd backend && ../.venv/bin/python -m pytest -q`.
- Never hardcode secrets. Never invent personal experiences, metrics, or sources. Publishing stays behind the kill switch.
- Skills must keep the section contract enforced by `backend/tests/test_skills.py`.
