# Sources and evidence

## Source tiers
| Tier | Examples | Use |
|---|---|---|
| 1 Primary | Official company blog/changelog, research paper, SEC filing, official docs, dataset | Facts and numbers |
| 2 Reputable reporting | Established tech/business press with named reporters | Context, corroboration, quotes |
| 3 Expert commentary | Named practitioners' blogs, newsletters, talks | Opinions, interpretation, labelled as opinion |
| 4 Community signal | HN threads, Reddit, public LinkedIn posts | Evidence that a discussion exists, never evidence of facts |

## Claim labels
| Type | Rule |
|---|---|
| fact | Needs a tier 1–2 source |
| statistic | Needs a tier 1 source, or tier 2 that names the original |
| opinion | Attribute it to a person or organisation |
| estimate | State the method or present as illustrative |

| Status | Meaning | Allowed in auto-published posts? |
|---|---|---|
| verified | Cited URL was retrieved and a quote supports the claim | Yes |
| sourced | Cited URL was retrieved, no supporting quote captured | Yes, if not a statistic |
| unsupported | No retrieved source | No. Remove or send to review |

## Freshness
Score = 10 × 0.5^(age_hours / half_life_hours), half-life 48h by default (`config/scoring.yaml`). Unknown date → 3.0.
