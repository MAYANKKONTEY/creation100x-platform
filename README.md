# Creation100x-platform
AI-powered content strategy, storytelling, and distribution systems that help founders turn attention into customers.

The first system in this platform is **LinkedIn Growth OS**, described below.

---

## LinkedIn Growth OS

An AI content intelligence and distribution system for one LinkedIn personal profile. It discovers topics, researches them against real sources, drafts posts and visuals in the owner's voice, runs quality gates, publishes through LinkedIn's official API, and learns from real performance.

It is not an engagement bot. No pods, fake engagement, automated comments, or scraping behind logins.

**Status:** Milestone 1 of 9 complete (foundation, database, discovery, research, Claude integration). See `TASKS.md`.

| Doc | What's in it |
|---|---|
| `ARCHITECTURE.md` | Components, data model, flows, integration gaps, trade-offs |
| `IMPLEMENTATION_PLAN.md` | Milestones M1–M9 with acceptance criteria |
| `TASKS.md` | Checklist, owner inputs needed, known limitations |
| `SKILLS_INDEX.md` | The 13 Claude Code skills and how the pipeline uses them |

### Quick start (backend)

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -e "backend[dev]"
```

```bash
cp .env.example .env
```

Add `ANTHROPIC_API_KEY` to `.env` to enable research. Everything else works without it.

```bash
cd backend && ../.venv/bin/python -m app.cli seed-sources
```

```bash
cd backend && ../.venv/bin/python -m app.cli discover
```

```bash
cd backend && ../.venv/bin/python -m app.cli research "AI coding agents and junior developer hiring"
```

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload
```

The API docs are at `http://localhost:8000/docs`.

### Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

Tests need no network and no API keys. HTTP uses `httpx.MockTransport`, and the Claude SDK is replaced by a fake.

### Key API endpoints (M1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | DB, LLM configured, publishing state, skill count |
| GET/POST/PATCH | `/api/sources`, `/api/sources/seed` | Manage discovery sources |
| POST | `/api/discovery/run` | Fetch all enabled sources |
| GET | `/api/items` | Discovered items (filter by category, date, text) |
| POST/GET | `/api/opportunities`, `/api/opportunities/{id}/score` | Create and score opportunities |
| GET | `/api/scoring/models` | Current weights and versions |
| POST/GET | `/api/research`, `/api/research/{id}` | Research briefs with verified claims |
| GET/POST | `/api/safety`, `/api/safety/emergency-stop`, `/api/safety/enable-publishing` | Kill switch |
| POST/GET | `/api/brand-voice/samples` | Writing samples |
| GET | `/api/jobs`, `/api/llm-calls`, `/api/skills` | Logs and skills library |

### Safety defaults
- Publishing needs **both** `PUBLISHING_ENABLED=true` in env **and** the DB flag, which is set with the exact phrase `ENABLE PUBLISHING`. Both are off by default.
- `POST /api/safety/emergency-stop` turns publishing off immediately.
- A claim is `verified` only when a quote appears verbatim in citation text from a URL that web search actually returned.

### Layout
```
.claude/skills/        13 skills (Claude Code + runtime prompt modules)
backend/app/           FastAPI app: config, db, models, llm, skills, discovery, research, scoring, safety, api
backend/tests/         pytest suite
config/                sources.yaml, scoring.yaml, pricing.yaml
brand/                 voice-profile.md
```
