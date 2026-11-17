---
name: hook-engineering
description: Generate at least 10 LinkedIn hooks per topic across 10 hook types and score each on clarity, relevance, curiosity, specificity, credibility and originality, rejecting misleading clickbait. Use whenever opening lines or headlines are needed.
---

# Hook Engineering

## Purpose
Produce the opening line(s) that decide whether someone taps "…see more". A strong hook is honest about what the post delivers.

## Instructions
- Generate **≥ 10 hooks**, at least one per type: contrarian, controversial-but-defensible, curiosity, unexpected insight, data-driven, problem-focused, storytelling, comparison, question, strong opinion. Definitions and patterns are in `references/hook-types.md`.
- Hooks are 1–2 lines and roughly 150 characters or fewer, so the point lands before truncation.
- Data-driven hooks may only use numbers present in the research brief with a source.
- Storytelling hooks need an owner-supplied story. Otherwise write them as third-person or hypothetical and label them that way.
- **Clickbait test:** would a reader who finished the post feel the hook was honest? If not, reject it. Reject hooks that promise secrets, use fake urgency, or claim something the body does not support.
- Score each hook 0–10 on six dimensions and give a one-line rationale. Total = mean × 10 (0–100). Scores are for ranking, not predicting reach.

## Workflow
1. Read the brief and the chosen angle. Write down the one insight the post delivers.
2. Draft 2 hooks per type (20), then cut to the best 10–12.
3. Run the clickbait test and drop failures.
4. Score the rest on the six dimensions.
5. Return them ranked, with the top 3 flagged and a recommended A/B pair (two different types, similar scores).

## Reusable prompts
```
Insight the post delivers: {insight}
Verified facts available: {claims}
Write 20 hooks (2 per type) for these types: {types}. Max 150 characters each.
Then remove any that overpromise relative to the insight. Score the remaining
on clarity, relevance, curiosity, specificity, credibility, originality (0-10, one-line reason each).
```

## Examples
### Good
- *Data-driven:* "Stack Overflow's 2024 survey: 76% of developers use or plan to use AI tools. Trust in their output is a different story." (number from a cited source, with an honest tension)
- *Contrarian:* "Your AI agent doesn't need more tools. It needs fewer."
- *Comparison:* "RAG vs. long context: I stopped asking which is better and started asking which fails more gracefully." (Okay only if the owner did this. Otherwise reword to "Teams should stop asking…".)

### Bad
- "This ONE trick will 10x your startup (nobody talks about it)." Vague, overpromises, fake secrecy.
- "OpenAI is finished." Unsupported and sensational.
- "I fired my whole team for AI." Invented experience, outrage bait.

## Quality checklist
- [ ] ≥ 10 hooks covering all 10 types
- [ ] Each ≤ ~150 characters and makes sense alone
- [ ] Numbers trace to brief sources
- [ ] No invented personal stories
- [ ] Clickbait test applied; failures removed with reason
- [ ] Six sub-scores + rationale per hook; ranked; A/B pair suggested

## Output structure
```json
{
  "insight": "",
  "hooks": [
    {"text": "", "type": "contrarian",
     "scores": {"clarity": 0, "relevance": 0, "curiosity": 0, "specificity": 0, "credibility": 0, "originality": 0},
     "rationale": {"clarity": ""}, "total": 0, "uses_source_urls": []}
  ],
  "rejected": [{"text": "", "reason": ""}],
  "top3": [0, 1, 2],
  "ab_pair": [0, 3]
}
```
