---
name: content-distribution
description: Plan the content calendar, balance content pillars and formats, choose publish times from the owner's own data, and run pre-publish checks for the official LinkedIn API publisher, while refusing artificial engagement tactics. Use for scheduling, calendar planning and publishing decisions.
---

# Content Distribution

## Purpose
Publish one high-quality post a day, at sensible times, with a balanced mix, through official channels only.

## Instructions
- **Cadence:** target one post a day. Generate 3 candidates and publish the best one that passes every gate. If none passes, publish nothing that day. Skipping beats shipping weak content.
- **Pillar balance (rolling 14 days):** no pillar above 35%. Rotate formats so the same format doesn't run 3 days in a row. Pillars: AI engineering · LLMs & agents · AI tools & experiments · software development · startup building · entrepreneurship · marketing & distribution · business models · creator economy · building in public.
- **Timing:** start with weekday mornings in the owner's timezone as a hypothesis. Replace it with the owner's own data once `linkedin-analytics` has enough posts (≥ 20 per slot). Never present a "best time" claim as universal fact.
- **Official API only.** Use the LinkedIn Posts API with OAuth and the owner's consent scopes. Respect rate limits, back off on 429, and use an idempotency key per publish so a retry never double-posts.
- **Never:** engagement pods, automated comments or likes, fake accounts, tagging people who aren't involved, "comment YES to get the PDF" bait, or reposting the same content to game reach.
- **Kill switch** is checked immediately before every API call. If it's off, abort and log.
- After publishing, read the post back from the API to verify it exists, then store the URN and URL. If verification fails, mark the post `unverified` and alert. Never assume success.

## Workflow
1. Take today's gated candidates (decision = auto_publish) and the review-queue approvals.
2. Check pillar and format balance against the last 14 days. Pick the best candidate that keeps balance.
3. Choose a slot from the schedule (hypothesis or data-driven).
4. Pre-publish checks: kill switch, token validity, media uploaded and processed, text ≤ 3,000 characters, no unresolved `[OWNER INPUT NEEDED]` markers, links valid.
5. Publish → verify → store → schedule metric collection (+2h, +24h, +72h, +7d).
6. Log the decision and the reasons.

## Reusable prompts
```
Last 14 days of posts: {history}. Candidates (passed gates): {candidates}.
Pick one candidate that keeps pillar share ≤ 35% and avoids 3 same-format days in a row.
Explain the choice in 2 sentences. If no candidate fits, say "skip".
```

## Examples
### Good
"Selected candidate B (pillar: business models, format: breakdown). AI engineering is already at 33% over 14 days, and yesterday was also technical. Slot 08:30 local (hypothesis, 6 posts of data so far)."

### Bad
"Post all 3 candidates today, tag 15 influencers, and ask a pod to comment in the first hour."

## Quality checklist
- [ ] Only gate-passing or human-approved content
- [ ] Pillar ≤ 35% and format rotation respected
- [ ] Kill switch and token checked right before the API call
- [ ] Idempotency key used; publish verified by read-back
- [ ] No artificial engagement tactics
- [ ] Timing claims labelled as hypothesis or data-backed

## Output structure
```json
{"date": "", "selected_candidate_id": null, "skip_reason": null, "slot": "08:30", "slot_basis": "hypothesis|data",
 "balance": {"pillar_share_14d": {}, "format_streak": 0},
 "prepublish_checks": {"kill_switch": "pass", "token": "pass", "media": "pass", "length": "pass", "markers": "pass"},
 "rationale": ""}
```
