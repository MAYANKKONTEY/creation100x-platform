# Tasks

Legend: `[x]` done and tested · `[ ]` open · `[~]` partial · ⚠ needs owner input or an external decision

## Owner inputs needed
- [ ] ⚠ `ANTHROPIC_API_KEY` in `.env`. Research cannot run live without it (it returns 503 today).
- [ ] ⚠ 5–15 writing samples for the Brand Voice Profile (`POST /api/brand-voice/samples`).
- [ ] ⚠ Owner timezone (`OWNER_TIMEZONE`) for scheduling.
- [ ] ⚠ Recorded positions on recurring debates (open vs closed models, AI and junior devs, …) so opinion posts don't need review every time.
- [ ] ⚠ LinkedIn developer app (M7): create the app and add "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect".
- [ ] ⚠ `OPENAI_API_KEY` (M5).
- [ ] ⚠ Hosting choice (M9): single VM with Docker Compose, or a managed platform.
- [ ] ⚠ Git remote: where should this repo live?

## M1 — Foundation, database, research, Claude integration
- [x] Repo layout, `.gitignore`, `.env.example`, `pyproject.toml`
- [x] Settings via environment (`pydantic-settings`); app boots without secrets
- [x] SQLAlchemy models: Source, RawItem, Opportunity, ResearchBrief, Evidence, Claim, WritingSample, Setting, JobRun, LLMCall
- [x] `ClaudeClient`: structured output, adaptive thinking, explicit effort, server-side refusal fallback, web search with `pause_turn` continuation, typed errors, usage logging
- [x] `FakeLLM` for tests
- [x] `SkillLoader` with contract validation; 13 skills pass
- [x] RSS/Atom + HN Algolia connectors; URL normalisation; de-duplication; per-source failure isolation
- [x] 15 vetted sources in `config/sources.yaml` (live run: 15/15 OK, 324 items)
- [x] Research service: two-step research plus deterministic claim verification (verbatim-quote rule)
- [x] Scoring engine: 3 models from YAML, validation, breakdown, version, freshness decay
- [x] Kill switch: env + DB, default off, confirmation phrase to enable, emergency stop
- [x] JobRun audit; LLM usage kept even when a job fails
- [x] REST API (health, sources, discovery, items, opportunities, scoring, research, safety, brand voice, jobs, llm-calls, skills)
- [x] CLI: `seed-sources`, `discover`, `research`
- [x] 66 tests passing
- [ ] Live research run against the Claude API (blocked on API key)
- [ ] PostgreSQL run (code is dialect-neutral; untested against a real Postgres instance)

## M2 — Viral discovery, AI trend radar, business intelligence
- [x] Triage stage: batched Claude classification (category, pillar, story key, 5 sub-scores + reasons) with code validation of ids, pillars and ranges
- [x] Stale filter (older than 96h never sent to Claude) and per-run item cap for cost control
- [x] Story clustering: Claude story keys (shown recent keys to reuse) + title-similarity backstop; one Opportunity per story
- [x] Real coverage signals per opportunity (items, distinct sources, max HN points / GitHub stars)
- [x] GitHub search connector (official API; "new repos by stars", not "trending"), optional `GITHUB_TOKEN`
- [x] GitHub clone-network filter: name/description shared by ≥3 owners dropped, 2 owners flagged
- [x] Swipe file for pasted public LinkedIn posts + pattern extraction with a 6-word copy guard
- [x] Per-opportunity analysis (why it matters, angles, business implication, visual direction, research questions, sensitivity → review)
- [x] Pillar-balanced selection of the top opportunities
- [x] Trend radar, business radar, story detail, pattern summary endpoints
- [x] `python -m app.cli pipeline` (discover → triage → select → analyse), cron-friendly until the M7 scheduler
- [x] 90 tests passing
- [ ] Live triage/analysis run against Claude (blocked on API key)
- [ ] Tune `min_audience_relevance` and triage effort on real output

## M3 — Business problems, startup opportunities, controversy
- [ ] Business problem extraction + radar endpoint
- [ ] Startup opportunity records (evidence strength, speculative flag)
- [ ] Controversy engine + safety guards + seeded debates

## M4 — Writing Studio, hooks, brand voice
- [ ] Brand voice extraction + similarity check
- [ ] Hook engine (≥10 hooks, 6 sub-scores, clickbait filter)
- [ ] Three-variant drafting across formats and frameworks
- [ ] Writing gates + Post Quality Score + semantic fact-check gate (claim vs quote entailment)

## M5 — Visuals and carousels
- [ ] HTML/CSS templates + Playwright rendering (PNG, PDF)
- [ ] OpenAI Images integration (verify current model and params first)
- [ ] Visual QA (contrast, font size, overflow, vision review) + Visual Quality Score

## M6 — LinkedIn SEO
- [ ] Keyword extraction, placement and density checks, hashtag policy
- [ ] Ranking-awareness checklist, profile alignment report, article SEO package

## M7 — LinkedIn API + publishing
- [ ] Confirm current LinkedIn API docs; write `docs/linkedin-api-notes.md`
- [ ] OAuth, encrypted tokens, expiry alerts
- [ ] Media upload, post creation, read-back verification, idempotency
- [ ] Persistent scheduler + worker; review queue; daily cycle

## M8 — Analytics and learning
- [ ] Metric collection (API where permitted) + CSV/XLSX import fallback
- [ ] Experiments with sample-size guardrails; bounded learning loop

## M9 — Dashboard and deployment
- [ ] Next.js dashboard (21 pages) + auth
- [ ] Alembic baseline; Docker; deploy guide; backups; alerting; E2E smoke tests

## Known limitations (M1)
- Claim verification proves a quote exists on a retrieved page. It does not yet prove the quote *supports* the claim; that's the M4 fact-check gate.
- A number written differently ("76%" vs "76 percent") downgrades a claim to `sourced`. Conservative by design.
- Discovery runs synchronously inside the API request; it moves to the worker in M7.
- No dashboard authentication yet (M9). Do not expose the API publicly.

## Known limitations (M2)
- Opportunity analysis uses headlines and summaries only. It is stored as `verified: false` until research runs.
- Story merging can miss two very differently worded headlines if Claude gives them different keys. It can also wrongly merge two different stories whose titles share most words (threshold 0.6, configurable).
- Opportunity sub-scores are the element-wise maximum across a story's items. More coverage can raise a score but never lower it.
- GitHub topic search is heavily polluted by star-farmed clones (94 of the top 100 new `llm` repos on 2026-11-17). The filter removes networks of 3+ owners, but a farm using unique names would get through.
- Schema changed (stories, triage fields, swipe posts). With no migrations until M9, delete `data/growthos.db` when upgrading a dev database.
- The end-to-end analysis cost per run is unmeasured until a live run. Estimate: about 10 triage batches (low effort) plus 5 analyses (medium effort) per day.
