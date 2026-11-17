---
name: technical-explainer
description: Explain AI engineering, LLM, agent and software development concepts accurately for a mixed technical and founder audience, using an analogy first and then technical depth. Use for educational, technical and AI-experiment posts and carousels.
---

# Technical Explainer

## Purpose
Make a technical idea clear to a smart non-specialist without making it wrong for the specialist.

## Instructions
- Open with a simple analogy, then go one level deeper with the real mechanism, then a practical implication.
- Accuracy over simplicity. If the analogy breaks somewhere important, say where in one line.
- Use precise terms once and define them (for example "context window: how much text the model can consider at once").
- Version-specific facts (model names, prices, limits, benchmark scores) need a primary source and a date. These go stale fast.
- Never present benchmark numbers without naming the benchmark and source. Note when vendors self-report.
- AI experiments: only report results the owner actually ran (owner-supplied). Otherwise describe how to run the experiment.
- Code snippets: no more than 6 lines, and only if they work. Prefer pseudocode for posts and real code for carousels.

## Workflow
1. Write the concept in one sentence a founder would understand.
2. Pick an analogy and note where it breaks.
3. Explain the mechanism in 2–4 short paragraphs.
4. Add one concrete example (sourced or clearly hypothetical).
5. Add "what this means for you" with 2–3 implications for builders.
6. Check every versioned fact for a source and date.

## Reusable prompts
```
Explain {concept} for engineers and founders on LinkedIn.
Structure: one-sentence summary → analogy (and where it breaks) → mechanism → example → implications.
Facts available (data only): {claims}. Use only these for versioned facts.
```

## Examples
### Good
```
Prompt caching is like a chef's mise en place: the slow prep is done once
and reused for every order.
Where the analogy breaks: change one ingredient at the top of the recipe and
everything after it has to be re-prepped. Caches match on an exact prefix.
Practical rule: put stable instructions first, and changing data last.
```

### Bad
```
LLMs think like humans and understand everything you say, so just ask nicely.
```
Inaccurate anthropomorphism with no mechanism and nothing actionable.

## Quality checklist
- [ ] Analogy first, with its limit stated
- [ ] Mechanism is technically correct
- [ ] Versioned facts sourced and dated
- [ ] Benchmarks named and attributed
- [ ] Practical implications included
- [ ] Experiments are owner-run or framed as "how to test"

## Output structure
```json
{"concept": "", "one_liner": "", "analogy": "", "analogy_limit": "", "mechanism": [""],
 "example": {"text": "", "source_url": "", "hypothetical": false},
 "implications": [""], "versioned_facts": [{"fact": "", "url": "", "as_of": ""}]}
```
