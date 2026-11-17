---
name: content-quality
description: Run the final quality gates on a post and its visuals (fact check, source verification, originality, writing quality, SEO, visual QA, brand voice, platform policy, publishing validation), compute the Post Quality Score and decide auto-publish, review or reject. Use before anything is scheduled or published.
---

# Content Quality

## Purpose
Be the editor who says no. Nothing reaches LinkedIn unless every configured gate passes. Anything uncertain goes to a human.

## Instructions
- Each gate returns `pass`, `fail`, or `uncertain`, with reasons.
- **Decision rule:** all pass → `auto_publish`. Any `uncertain`, or a `sensitive` flag → `review`. Any `fail` → `reject` (with fix suggestions) or `review` if it can be fixed by a human.
- Deterministic checks run first (cheap, reliable). LLM judgement only covers what code can't check.
- **Post Quality Score** (heuristic, 0–100): hook 20 · information value 20 · audience relevance 20 · originality 15 · readability 10 · credibility 15. Minimum to auto-publish: configurable (default 70).

## Gates
| Gate | Deterministic checks | LLM checks |
|---|---|---|
| Fact check | Every statistic/fact sentence maps to a claim with status verified/sourced | Does the post's wording overstate the claim? |
| Source verification | Source URLs resolve (HTTP 2xx/3xx) and were in the research set | — |
| Originality | n-gram overlap with sources and past posts below threshold; no copied swipe-file text | Is there a perspective beyond restating news? |
| Writing quality | Paragraph ≤ 3 lines, length within format range, banned-phrase list, repeated openings | Clarity, flow, filler |
| SEO | Primary keyword in first 2 lines, density ceiling, hashtags ≤ 3 | Natural-sounding keyword use |
| Visual | Dimensions, contrast, font size, overflow, spell check | Vision review score ≥ threshold |
| Brand voice | Style metrics within profile ranges; no `[OWNER INPUT NEEDED]` left | Sounds like the owner? Opinions consistent with owner's stated positions? |
| Platform policy | No engagement bait patterns, no mass tagging, no prohibited content | Misleading or harmful framing? |
| Publishing validation | ≤ 3,000 chars, media present and processed, links valid, kill switch on | — |

## Workflow
1. Run deterministic checks for all gates.
2. Run LLM checks only for gates that passed their deterministic stage.
3. Compute the Post Quality Score.
4. Apply the decision rule and list required fixes.
5. Record a `QualityReport`.

## Reusable prompts
```
Post: <post>{post}</post>  Claims with status: {claims}  Voice profile: {voice}
For each LLM-checked gate (fact wording, originality, writing, SEO naturalness, brand voice, policy framing)
return pass|fail|uncertain with reasons. Use "uncertain" whenever you are not confident.
Then score: hook, information_value, audience_relevance, originality, readability, credibility (0-10 each).
```

## Examples
### Good
Decision `review`: "Brand voice uncertain. The post takes a strong stance on open-source models, and the voice profile has no recorded position on this. All other gates pass. PQS 78."

### Bad
Decision `auto_publish` while a statistic ("70% of startups fail at AI") has status `unsupported`. The fact-check gate was skipped.

## Quality checklist
- [ ] All 9 gates evaluated; none skipped
- [ ] Deterministic checks before LLM checks
- [ ] Unsupported claims → fail
- [ ] Uncertain → review, never auto-publish
- [ ] PQS computed with stored weight version
- [ ] Fix list is concrete

## Output structure
```json
{"gates": [{"gate": "fact_check", "result": "pass", "reasons": [], "checks": {}}],
 "scores": {"hook": 0, "information_value": 0, "audience_relevance": 0, "originality": 0, "readability": 0, "credibility": 0},
 "post_quality_score": 0, "scoring_version": "",
 "decision": "auto_publish|review|reject", "required_fixes": [], "sensitive": false}
```
