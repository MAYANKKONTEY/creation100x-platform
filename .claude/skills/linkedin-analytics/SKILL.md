---
name: linkedin-analytics
description: Analyse real LinkedIn post performance (impressions, reactions, comments, reposts, engagement rate, follower growth where accessible), run fair A/B experiments, and turn results into bounded, reversible recommendation updates without over-claiming causation. Use for performance reviews, experiment design and the learning loop.
---

# LinkedIn Analytics

## Purpose
Learn what actually works for this audience from real data, slowly and honestly.

## Instructions
- Use only metrics the API or LinkedIn's own export provides. A missing metric is `null`, never estimated or filled in.
- **Engagement rate** = (reactions + comments + reposts) / impressions, computed only when impressions are known. Always show the denominator.
- Compare like with like: same metric age (for example the 72h snapshot), similar weekday and time window, same format.
- **Small samples:** with fewer than 5 posts per arm, report descriptively only ("A: 3 posts, median 1,200 impressions"). Do not declare winners.
- **Causation:** one post outperforming says almost nothing. Phrase findings as "associated with" unless a controlled experiment supports more.
- Comments are the strongest signal of meaningful conversation. Weight comment quality (replies with substance) over raw counts when reviewing.
- Account for confounders: news cycles, reshares by large accounts, holidays, format changes.

## Experiments
| Experiment | Variable | Held constant |
|---|---|---|
| Hook A vs B | Hook type | Topic pillar, format, time slot, visual style |
| Editorial vs cinematic image | Visual concept | Text, pillar, slot |
| Text vs image | Media presence | Pillar, hook type, slot |
| Educational vs opinion | Format | Pillar, slot, media |
| Pillar comparison | Pillar | Format, slot, media |

LinkedIn does not offer split-testing for personal posts. Experiments run **sequentially**: alternate arms across comparable days. Minimum 5 posts per arm before any directional conclusion, and 10+ before acting on it.

## Learning loop
1. Weekly: aggregate the 72h snapshots by hook type, topic, format, visual style, and slot.
2. Compute medians and interquartile ranges (robust to one viral outlier).
3. For experiments with enough data, report the difference in medians with a bootstrap interval.
4. Propose bounded updates to selection weights (max ±10% per week per factor). Log them and keep them reversible.
5. Never reduce a pillar below 10% share on performance alone. That protects topic consistency and stops the system from chasing noise.

## Workflow
1. Pull new metric snapshots (API or imported export).
2. Validate (no negative values, impressions ≥ reactions).
3. Update aggregates and experiments.
4. Write the weekly report: what we know, what we don't, proposed changes, and confidence.

## Reusable prompts
```
Aggregates (data only): {aggregates}. Experiments: {experiments}.
Write a weekly report: findings phrased with appropriate confidence ("associated with", sample sizes shown),
unknowns, proposed bounded weight changes (≤ ±10%), and next experiments. Do not claim causation from single posts.
```

## Examples
### Good
"Question hooks: 7 posts, median 72h impressions 1,840 (IQR 1,200–2,300). Statement hooks: 9 posts, median 1,410. The difference is directional; the intervals overlap. Proposed: +5% weight on question hooks, revisit after 5 more posts each."

### Bad
"Our carousel got 10k impressions, so carousels are 5× better. Switch everything to carousels."

## Quality checklist
- [ ] Only real metrics; nulls preserved
- [ ] Engagement rate shows its denominator
- [ ] Comparisons use the same snapshot age and comparable conditions
- [ ] Sample sizes shown; no winners under 5 per arm
- [ ] Causal language avoided unless justified
- [ ] Weight changes bounded, logged, reversible

## Output structure
```json
{"period": "", "posts_analyzed": 0,
 "by_dimension": {"hook_type": [{"value": "", "n": 0, "median_impressions": null, "iqr": [null, null], "median_er": null}]},
 "experiments": [{"name": "", "arms": {}, "status": "collecting|directional|actionable", "difference": null, "interval": null}],
 "proposed_weight_changes": [{"factor": "", "from": 0, "to": 0, "reason": ""}],
 "unknowns": [""], "confidence_note": ""}
```
