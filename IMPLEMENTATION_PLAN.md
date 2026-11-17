# Implementation Plan

Each milestone ships working, tested code and ends with a report of actual test results and unfinished work. A milestone does not start until the previous one is reviewed.

## M1 — Foundation, database, research, Claude integration ✅ (this delivery)

**Goal:** a running FastAPI backend that can ingest real sources, store them, research a topic with verifiable sources, and score opportunities with a configurable model.

| Deliverable | Acceptance |
|---|---|
| Project layout, settings, `.env.example` | App boots with zero secrets, and LLM features report "not configured" instead of crashing. |
| SQLAlchemy models + session | SQLite file DB in dev; `DATABASE_URL` switches to PostgreSQL. |
| `ClaudeClient` | Structured output via Pydantic, web search with source extraction, `pause_turn` handling, refusal → typed error, usage logged to `LLMCall`. |
| Skill loader | Loads all 13 skills and validates frontmatter and required sections (enforced by tests). |
| Discovery framework | RSS/Atom + HN Algolia connectors, URL normalisation, de-duplication, per-source error isolation, `JobRun` audit. |
| Research service | Two-step research. Claims are labelled `verified` / `sourced` / `unsupported` by deterministic checks. |
| Scoring engine | Three models from YAML, weights validated (sum to 1), breakdown and version stored, freshness decay. |
| Kill switch | Env and DB flags, emergency-stop endpoint, default **off**. |
| REST API | health, sources, discovery run, items, opportunities, scoring, research, safety, brand-voice samples, jobs, LLM calls, skills. |
| CLI | `seed-sources`, `discover`, `research "<topic>"`. |
| Tests | Unit and API tests with fakes. No network or API key needed. |

## M2 — Viral discovery, AI trend radar, business intelligence

- More connectors: GitHub search API (trending repos by stars/day), Product Hunt (if token provided), more vetted feeds. A "swipe file" endpoint for pasting public LinkedIn posts.
- **Triage stage:** Claude batch-classifies new items into categories A–E and sub-scores (audience relevance, business importance, discussion potential, virality hypothesis, evidence quality). Freshness is computed. Opportunity rows are created with score breakdowns.
- Clustering: group items about the same story (title-embedding or LLM clustering) so one story does not show up as five opportunities.
- Content pattern analysis (`viral-research` skill): from swipe-file posts, extract hook structure, format, and topic patterns as abstract, reusable patterns. No copying.
- Per-opportunity analysis: why it matters, why people discuss it, pain point, original/contrarian/educational angle, business implication, visual direction.
- API: trend radar, business intelligence feeds with filters.
- Tests: triage with `FakeLLM`, clustering, pattern extraction schema.

## M3 — Business problems, startup opportunities, controversy intelligence

- Business-problem radar: extract problem statements (who, pain, current workaround, cost signals, evidence).
- Startup-opportunity records for Creation100x: underserved market, manual workflow, AI automation angle, evidence strength, and an explicit "speculation" flag.
- Controversy engine: main argument, opposing argument, supporting evidence, counter-evidence, nuance, defensible position, discussion question. Hard guard against personal attacks, false scandals, and claims that lack evidence.
- Seeded debate topics from the brief (AI vs developers, AI content, open vs closed models, …).
- Tests: schema validation, guard rules (names of private individuals, unsupported accusations → rejected).

## M4 — Skills in production, Writing Studio, hook engineering

- Brand Voice Profile extraction from writing samples (sentence length, vocabulary, stance markers, banned phrases). Voice similarity check.
- Hook engine: ≥10 hooks across 10 types. Six sub-scores (clarity, relevance, curiosity, specificity, credibility, originality). Clickbait detector.
- Drafting: three variants per topic across the 12 formats and 6 formulas, each with the 10 required parts.
- Writing gates: readability (mobile line length, paragraph length), AI-cliché blacklist, repetition detector, claim-to-source linkage, originality (n-gram overlap against sources and past posts).
- Post Quality Score.
- Tests: gates on fixture posts (good and bad), score maths, prompt assembly.

## M5 — Visual design, image generation, carousels

- Three visual concepts per post (editorial typography, cinematic tech, infographic).
- HTML/CSS templates (Jinja2 + a shared design-token CSS) rendered with Playwright to PNG (1080×1350, 1200×627, 1080×1080) and multi-page PDF carousels.
- OpenAI Image API integration for artwork only. Model name and parameters confirmed from current docs at implementation time.
- Visual QA: dimensions, contrast ratio (WCAG) computed from tokens, min font size at mobile scale, text-overflow detection in DOM, plus a Claude vision review of the rendered image. Visual Quality Score.
- Tests: render snapshots, contrast maths, overflow detection.

## M6 — LinkedIn SEO and content optimisation

- Keyword extraction (primary, secondary, related phrases, intent) and natural-placement checks (subject in first 2 lines, density ceiling).
- Hashtag policy (0–3, only when relevant).
- Profile alignment report: headline, About, skills against published topic clusters.
- Article/newsletter SEO package: title, description, headings.
- Ranking-awareness checklist (10 dimensions). Explicitly heuristic.
- Tests: keyword stuffing detector, checklist generation.

## M7 — Official LinkedIn API and automatic publishing

- Confirm current LinkedIn API docs (version header, scopes, token lifetime, document posts) before writing any code. Record the findings in `docs/linkedin-api-notes.md`.
- OAuth 2.0 authorization-code flow, encrypted token storage, expiry alerts.
- Upload images and documents, create posts, then read back to verify. Store URN and URL.
- Persistent scheduler + worker. Daily cycle: 3 candidates → gates → 1 auto-published or queued.
- Rate-limit handling, idempotency keys (never double-post), kill switch checked immediately before the API call.
- Review queue with approve / edit / reject.
- Tests: OAuth state/CSRF, publisher against a mocked LinkedIn API, idempotency, kill-switch race.

## M8 — Analytics, experiments, learning engine

- Metric collection from the API where permitted. CSV/XLSX import of LinkedIn's analytics export as a fallback.
- Performance views by hook type, topic, format, visual style, posting time.
- A/B experiments run sequentially with comparable conditions (same weekday/time window, same pillar). Results report effect size with uncertainty, and the system refuses to declare a winner on small samples.
- Learning loop: bounded adjustments to selection weights (for example ±10% per cycle), always logged and reversible.
- Tests: statistics helpers, guardrails, import parser.

## M9 — Dashboard, deployment, production reliability

- Next.js dashboard with all 21 pages.
- Auth for the dashboard.
- Alembic baseline migration, PostgreSQL.
- Dockerfiles + `docker-compose.yml` (api, worker, frontend, db). Deployment guide for one cloud target.
- Backups (`pg_dump` daily, 14-day retention), health checks, alerting (email or Slack webhook) on failed jobs, token expiry, or kill-switch trips.
- E2E smoke test with Playwright.
