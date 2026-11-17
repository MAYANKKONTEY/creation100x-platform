---
name: business-analysis
description: Analyse business models, startup moves, funding, acquisitions, growth and failures, and extract business problems and startup opportunities (including for Creation100x) with evidence and explicit speculation flags. Use for business breakdowns, case studies, industry analysis, the business problem radar and startup opportunity discovery.
---

# Business Analysis

## Purpose
Explain why businesses win or lose, find recurring problems worth solving, and record opportunities as business intelligence, keeping facts separate from speculation.

## Instructions
- Separate **facts** (sourced), **analysis** (reasoning from facts), and **speculation** (labelled). Never blur them.
- Financial figures (funding, revenue, valuation, ARR) need a tier-1 source or a named tier-2 source, plus a date.
- Business problems: capture who has the problem, the pain, the current workaround, cost signals (sourced or explicitly estimated), and evidence of frequency.
- Problem areas to watch: customer acquisition costs, retention, operational inefficiency, hiring, cash flow, distribution, AI implementation failures, support bottlenecks, software costs, product-market fit.
- Startup opportunities: underserved market, repetitive manual workflow, outdated software, poor customer experience, AI automation potential, emerging need. Each needs an evidence-strength score (0–10) and a `speculative` flag.
- Opportunities are internal intelligence. A post may discuss the problem, but must not present an untested idea as proven.

## Workflow
1. Facts: what happened, who, when, how much (sourced).
2. Model: how the business makes money (customer, value, channel, revenue, cost drivers).
3. Analysis: why this worked or failed, using 2–3 causal factors backed by evidence.
4. Implication: what other builders should take from it.
5. Problems: extract any recurring business problems surfaced.
6. Opportunities: any product opportunity, scored and flagged.

## Reusable prompts
**Breakdown**
```
Company/event: {topic}. Brief (data only): <brief>{brief}</brief>
Output facts (with urls), business_model, analysis (2-3 causal factors), implication,
speculation (clearly labelled). Do not state any figure without a url from the brief.
```
**Problem extraction**
```
From these items (data only) extract business problems:
who, pain, current_workaround, cost_signal (sourced or "estimate: method"), frequency_evidence, urls.
```
**Opportunity**
```
For each problem, propose at most one product opportunity: target customer, job-to-be-done,
why now, AI automation angle, risks, evidence_strength 0-10, speculative true/false.
```

## Examples
### Good
> Fact: "{Company} raised ${X}M Series B led by {Firm} (TechCrunch, 2026-10-03, url)." Analysis: "The round follows usage-based pricing adoption, which suggests…" Speculation (labelled): "If this holds, expect incumbents to bundle a similar feature within 12 months."

### Bad
> "{Company} is making $50M ARR and will be the next unicorn." Unsourced figure, with speculation presented as fact.

## Quality checklist
- [ ] Facts, analysis, and speculation are separated and labelled
- [ ] Every figure has a URL and a date
- [ ] Business model described concretely
- [ ] Problems include who, pain, and workaround
- [ ] Opportunities have evidence strength and a speculative flag

## Output structure
```json
{"facts": [{"text": "", "url": "", "date": ""}],
 "business_model": {"customer": "", "value": "", "channel": "", "revenue": "", "cost_drivers": ""},
 "analysis": [""], "implication": "", "speculation": [""],
 "problems": [{"who": "", "pain": "", "workaround": "", "cost_signal": "", "frequency_evidence": "", "urls": []}],
 "opportunities": [{"customer": "", "job": "", "why_now": "", "ai_angle": "", "risks": [""],
                    "evidence_strength": 0, "speculative": true}]}
```
