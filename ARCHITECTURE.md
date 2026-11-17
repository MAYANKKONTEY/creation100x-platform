# LinkedIn Growth OS — Architecture

## 1. What this system is

A single-user content operating system for one LinkedIn personal profile. It finds topics worth writing about, researches them against real sources, drafts posts and visuals in the owner's voice, puts every candidate through a set of quality gates, publishes through LinkedIn's official API, and learns from the performance data it can actually get.

**Analogy:** a small newsroom. Reporters (discovery connectors) bring in leads, a research desk (research service) checks facts, writers and designers (skills plus Claude) produce drafts, an editor (quality gates) decides what runs, the printing press (publisher) ships it, and the analytics desk reports what worked. The kill switch is the editor-in-chief pulling the edition.

### Design principles

| Principle | What it means in code |
|---|---|
| Evidence before prose | Claims are tied to URLs the search tool actually returned. Claims without a retrieved source are marked `unsupported` and block auto-publish. |
| Heuristic scores, never predictions | Every score stores its weights version and a disclaimer. Nothing is called a "virality probability". |
| Safe by default | Publishing is **off** until both the env flag and the DB flag are on. Any uncertain gate result goes to the review queue. |
| One source of truth for prompts | `.claude/skills/*/SKILL.md` is used by Claude Code *and* loaded at runtime by the backend's `SkillLoader`. |
| Progressive disclosure | Each pipeline stage loads only the skills it needs. Long reference material lives in `references/` and is loaded on demand. |
| Official APIs only | LinkedIn: official REST APIs with OAuth. Research: RSS, public APIs, Claude's web search tool. No scraping behind logins, no engagement automation. |
| Replaceable parts | Connectors, LLM client, image provider, and publisher sit behind small interfaces with fakes for tests. |

## 2. System context

```
                ┌─────────────────────────────────────────────────────────┐
                │                   LinkedIn Growth OS                    │
 RSS / Atom ───▶│ Discovery ─▶ Triage ─▶ Research ─▶ Angles ─▶ Hooks      │
 HN Algolia ───▶│     │                      │                    │       │
 arXiv     ───▶│     ▼                      ▼                    ▼       │
 Claude    ◀──▶│  RawItems             Evidence/Claims       Drafts (×3) │
 web_search     │                                                 │       │
                │                     Visuals (×3) ◀── OpenAI Images       │
                │                     HTML/CSS render ◀── Playwright       │
                │                                                 │       │
                │  SEO report ─▶ Quality gates ─▶ auto │ review │ reject  │
                │                                    │                    │
 LinkedIn API ◀─│ Publisher (OAuth, media upload, verify) ◀── Kill switch  │
 (official)  ──▶│ Analytics collector ─▶ Experiments ─▶ Learning loop     │
                └─────────────────────────────────────────────────────────┘
                         ▲
                 Next.js dashboard (21 pages) ── FastAPI REST
```

## 3. Components

### 3.1 Backend (`backend/app/`)

| Module | Responsibility | Milestone |
|---|---|---|
| `config.py` | Typed settings from environment (`pydantic-settings`). No secrets in code. | M1 |
| `db.py`, `models.py` | SQLAlchemy 2.0 engine, session, ORM models. SQLite in dev, PostgreSQL in prod. | M1 |
| `llm/` | `LLMClient` protocol, `ClaudeClient` (Anthropic SDK), `FakeLLM` for tests. Structured outputs, web search, refusal handling, usage logging. | M1 |
| `skills/loader.py` | Reads `.claude/skills/*/SKILL.md`, validates frontmatter, serves skill bodies and reference files to pipeline stages. | M1 |
| `discovery/` | Connector interface plus RSS/Atom and Hacker News (Algolia) connectors. URL normalisation and de-duplication. | M1 (framework), M2 (more sources, triage) |
| `research/` | Two-step research: (1) Claude with web search gathers sources, (2) structured extraction of claims, each checked against the retrieved source set. | M1 |
| `scoring/` | Configurable weighted scoring models loaded from `config/scoring.yaml`. Deterministic freshness decay. | M1 |
| `safety/` | Kill switch (env and DB flags), publishing guard. | M1 |
| `jobs.py` | `JobRun` audit trail for every background operation. | M1 |
| `intelligence/` | Trend radar, business-problem radar, startup-opportunity and controversy analysis. | M2–M3 |
| `writing/` | Hooks (≥10, scored), three post variants, brand-voice validation. | M4 |
| `visuals/` | Visual concepts, OpenAI image generation, HTML/CSS → PNG/PDF rendering, visual QA. | M5 |
| `seo/` | Keyword extraction, post SEO report, profile recommendations, ranking-awareness checklist. | M6 |
| `gates/` | Quality gate engine → `auto_publish` / `review` / `reject`. | M4–M7 |
| `linkedin/` | OAuth 2.0, token storage (encrypted), images/documents upload, Posts API, verification. | M7 |
| `scheduler/` | Persistent scheduler (APScheduler + SQLAlchemy job store) and worker process. | M7 |
| `analytics/` | Metric collection, CSV import fallback, experiments, learning loop. | M8 |
| `api/` | FastAPI routers. | M1+ |

### 3.2 Frontend (`frontend/`, M9)

Next.js (App Router) + TypeScript + Tailwind. Talks to the FastAPI REST API only. Pages: Overview, Viral Intelligence, AI Trend Radar, Business Intelligence, Business Problem Radar, Startup Opportunities, Research Library, Hook Studio, Writing Studio, Visual Design Studio, Carousel Studio, LinkedIn SEO, Content Calendar, Publishing Queue, Published Content, Analytics, A/B Experiments, Brand Voice, Claude Skills Library, Automation Settings, System Logs.

### 3.3 Skills (`.claude/skills/`)

13 skills, each a self-contained `SKILL.md` with frontmatter, workflow, prompts, examples, checklist, and output structure. See `SKILLS_INDEX.md`. The backend maps pipeline stages to skills:

| Stage | Skills loaded |
|---|---|
| Discovery triage | `viral-research`, `business-analysis` |
| Research | `viral-research` |
| Angles / controversy | `controversial-angle`, `business-analysis` |
| Hooks | `hook-engineering` |
| Drafting | `linkedin-writing` + one of `storytelling` / `technical-explainer` / `business-analysis` |
| Visuals | `visual-design`, `carousel-design` |
| SEO | `linkedin-seo` |
| Gates | `content-quality` |
| Scheduling | `content-distribution` |
| Learning | `linkedin-analytics` |

## 4. Data model

Implemented in M1 (✓) or planned (milestone noted).

| Entity | Key fields | |
|---|---|---|
| `Source` | name, kind (`rss`/`hn_algolia`/…), url, category, enabled, last_fetched_at, last_error | ✓ |
| `RawItem` | source_id, url, url_hash (unique), title, summary, published_at, fetched_at, category, signals (JSON, source-provided only) | ✓ |
| `Opportunity` | raw_item_id?, title, category, status, sub_scores, score_total, score_breakdown, scoring_version, why_it_matters, angles (JSON) | ✓ (angles filled M2–M3) |
| `ResearchBrief` | opportunity_id?, topic, summary, status, model, created_at | ✓ |
| `Evidence` | brief_id, url, title, publisher, page_age, cited_text, retrieved_at | ✓ |
| `Claim` | brief_id, text, claim_type (fact/statistic/opinion/estimate), source_urls, status (`verified`/`sourced`/`unsupported`) | ✓ |
| `WritingSample`, `BrandVoiceProfile` | raw samples; extracted voice traits | ✓ storage, M4 extraction |
| `Setting` | key/value (kill switch, etc.) | ✓ |
| `JobRun` | name, status, started/finished, stats, error | ✓ |
| `LLMCall` | purpose, model, tokens in/out, stop_reason, request_id, latency, est. cost | ✓ |
| `Controversy` | main/opposing argument, evidence, nuance, defensible position, question | M3 |
| `Hook` | text, type, six sub-scores, total | M4 |
| `PostDraft` | opportunity_id, format, framework, body, cta, keywords, sources, variant | M4 |
| `VisualAsset` / `Carousel` | concept, style, prompt, file path, render method, QA scores | M5 |
| `SeoReport` | primary/secondary keywords, intent, checks, recommendations | M6 |
| `QualityReport` | per-gate result (pass/fail/uncertain + reasons), decision | M4–M7 |
| `PublishJob` / `PublishedPost` | scheduled_for, state, linkedin URN, URL, verification result | M7 |
| `MetricSnapshot` | post_id, captured_at, impressions, reactions, comments, reposts (null when unavailable) | M8 |
| `Experiment` | hypothesis, variable, arms, assignment, result, confidence note | M8 |

## 5. Key flows

### 5.1 Daily cycle (target state, M7+)

1. **06:00 discovery**: all enabled connectors run; new items are de-duplicated by normalised URL hash.
2. **Triage**: Claude classifies each new item (category, audience relevance, discussion potential, business importance). Freshness is computed, not guessed. Opportunity score is calculated.
3. **Selection**: the top N opportunities, balanced across content pillars, go to research.
4. **Research**: evidence gathering plus claim checking. Briefs with too few verified claims are dropped.
5. **Create**: angles → ≥10 hooks → three post variants → three visual concepts per post → SEO report.
6. **Gates**: fact check, source verification, originality, writing quality, SEO, visual QA, brand voice, platform policy, publishing validation.
7. **Decision**: best passing variant is auto-scheduled; anything uncertain or sensitive goes to the review queue.
8. **Publish**: kill switch checked → media uploaded → post created → read back to verify → URN and URL stored.
9. **Learn**: metrics collected at +2h, +24h, +72h, +7d where the API allows; experiments updated; recommendation weights adjusted with guardrails.

### 5.2 Research (M1, implemented)

```
topic ──▶ Claude + web_search (server tool)
            │  collects: web_search_result blocks (url, title, page_age)
            │            text citations (url, cited_text)
            ▼
        retrieved source set  ──▶ Claude structured extraction (Pydantic schema)
                                      claims[] each with source_urls[]
                                            │
                                            ▼
                         claim checker (deterministic):
                         - every cited URL must be in the retrieved set
                         - has a matching cited_text quote → verified
                         - URL retrieved but no quote → sourced
                         - otherwise → unsupported
```

Sources come from tool-result blocks, not from model prose, so the model cannot invent a URL that ends up marked as verified.

### 5.3 Publishing safety

```
can_publish() = env PUBLISHING_ENABLED == true
                AND db setting publishing_enabled == true
                AND decision == auto_publish
                AND all gates == pass
                AND LinkedIn token valid
```

`POST /api/safety/emergency-stop` sets the DB flag to false immediately, cancels scheduled publish jobs (M7), and writes an audit entry. Turning publishing back on needs an explicit confirmation body.

## 6. External integrations: status and gaps

| Integration | Status | Notes / risks |
|---|---|---|
| Claude API (Messages, structured outputs, web search) | **Implemented M1** (needs `ANTHROPIC_API_KEY` to run live) | Default model `claude-opus-5-5` with adaptive thinking, explicit effort, and server-side refusal fallback. |
| RSS/Atom feeds | **Implemented M1** | Feeds in `config/sources.yaml` were checked for HTTP 200 on 2026-11-17. Anthropic's site has no `/rss.xml` (404), so it's left out; track it through web search instead. |
| Hacker News (Algolia API) | **Implemented M1** | Public, documented API. Points/comments are stored as source signals. |
| arXiv | **Implemented M1** via RSS (`cs.AI`, `cs.CL`) | |
| OpenAI Image API | **Missing (M5)** | Needs `OPENAI_API_KEY`. The current image model name will be checked against OpenAI's docs when M5 starts, not assumed. |
| Playwright (HTML → PNG/PDF) | **Missing (M5)** | Chromium is available in this dev container. The production image needs it installed. |
| LinkedIn OAuth + Posts/Images/Documents APIs | **Missing (M7)** | Needs a LinkedIn developer app with the "Share on LinkedIn" product (`w_member_social`) and "Sign In with LinkedIn using OpenID Connect". To verify in M7: current API version header, token lifetime and refresh-token availability for this app type, document (PDF) post support for members. |
| LinkedIn post analytics for a personal profile | **Uncertain (M8)** | Member-level post analytics through the API may need restricted product access. Fallback: import LinkedIn's own analytics export (CSV/XLSX) through the dashboard. Missing metrics are stored as `null`, never estimated. |
| LinkedIn articles / newsletters via API | **Likely unsupported** | To be confirmed in M7. Plan: generate the article plus its SEO package for manual publishing, and share the link via the API. |
| Public viral LinkedIn posts | **No permitted bulk API** | Inputs: (a) posts the owner pastes into a swipe file, (b) public posts surfaced by Claude web search, (c) licensed third-party datasets if added later. No logged-in scraping. |
| Reddit, Product Hunt, GitHub, X | **Optional (M2)** | Each needs its own API credentials and terms review. GitHub search API is the cheapest to add. |
| Hosting (runs with the laptop closed) | **Missing (M9)** | Docker images for API, worker, and frontend, managed PostgreSQL, daily `pg_dump` to object storage. |

## 7. Technology decisions and trade-offs

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Job queue | DB-backed `JobRun` + APScheduler (SQLAlchemy job store) + one worker | Celery + Redis | One user and about one post a day. Redis adds an extra service with no throughput benefit. Can be swapped behind the `jobs` interface if load grows. |
| Sync vs async DB | Sync SQLAlchemy 2.0 | Async | Simpler tests and fewer footguns. The pipeline is I/O-light and runs in workers. |
| Schema migrations | `create_all` in M1–M8, Alembic from M9 | Alembic now | No production data exists until M9. Alembic baseline is created before first deploy. |
| Text in visuals | HTML/CSS rendered by Playwright | Image-model text | Image models still misspell text. Rendered HTML is exact and testable. |
| Prompt storage | Skills on disk, versioned in git | DB-stored prompts | Reviewable diffs, shared with Claude Code, no drift. |
| Structured LLM output | `messages.parse` with Pydantic schemas | Regex/JSON parsing | Schema-validated output removes a whole class of parsing bugs. |

## 8. Security

- Secrets only from environment variables (`.env` locally, platform secret store in prod). `.env` is git-ignored and `.env.example` documents every variable.
- LinkedIn tokens encrypted at rest with a Fernet key from `TOKEN_ENCRYPTION_KEY` (M7).
- Dashboard behind authentication (M9). Single-user admin with a hashed password or an OAuth provider, and a CSRF-safe session.
- External content (feeds, web pages, search results) is treated as untrusted. It goes into prompts as clearly delimited data, and skills tell the model to ignore instructions found inside sources.
- Least-privilege LinkedIn scopes. No comment or reaction automation.
- Audit trail: `JobRun`, `LLMCall`, and publish logs.

## 9. Observability

- Structured logs (JSON in prod).
- `JobRun` and `LLMCall` tables back the System Logs page.
- Estimated cost per LLM call from `config/pricing.yaml` (dated, editable).
- Health endpoint reports DB connectivity, kill-switch state, and whether the LLM is configured.
