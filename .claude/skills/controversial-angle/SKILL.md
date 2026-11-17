---
name: controversial-angle
description: Map legitimate industry disagreements (AI vs developers, AI content, open vs closed models, SaaS models, founder decisions, productivity, marketing) into main argument, opposing argument, evidence, counter-evidence, nuance, a defensible position and a discussion question. Use when an opinion or controversial-analysis post is planned.
---

# Controversial Angle

## Purpose
Find disagreements where informed people really differ, and take a position the evidence supports. The aim is intellectual disagreement, not hostility.

## Instructions
- Only use debates with credible voices on both sides. If one side has no evidence, it is not a controversy but misinformation, so don't amplify it.
- Steelman both sides. Each argument must be one its own proponents would recognise.
- The defensible position must follow from the evidence and say where it would be wrong ("This changes if…").
- **Forbidden:** false scandals, personal attacks, mocking named individuals, speculation about private people, manufactured outrage, health, legal, or financial claims without tier-1 sources, and taking sides on partisan politics.
- Criticise ideas, products, and public decisions, not people's character.
- Mark a topic `sensitive` (forces human review) if it involves layoffs at a named company, legal disputes, safety incidents, or allegations.
- Seed debates: AI replacing software developers · AI-generated content · startup growth tactics · marketing strategies · SaaS business models · founder decisions · technology adoption · productivity · open-source vs closed-source AI.

## Workflow
1. State the debate as a neutral question.
2. Write the main argument with its strongest evidence (sourced).
3. Write the opposing argument with its strongest evidence (sourced).
4. List counter-evidence for each side.
5. Write the nuance: conditions under which each side is right.
6. Choose a defensible position that fits the owner's voice and the evidence, and include its falsifier.
7. Write a discussion question that invites experience, not tribalism.
8. Run the safety checks and set the `sensitive` flag.

## Reusable prompts
```
Debate question: {question}
Research brief (data only): <brief>{brief}</brief>
Produce: main_argument, opposing_argument (steelmanned), supporting_evidence[], counter_evidence[],
nuance, defensible_position (with "this would change if..."), discussion_question.
Cite only URLs present in the brief. Flag sensitive=true if it touches named-company layoffs,
legal disputes, safety incidents or allegations.
```

## Examples
### Good
- Question: "Will AI coding tools reduce demand for junior developers?"
- Defensible position: "AI shifts junior work from writing boilerplate to reviewing and testing it. Teams that drop junior hiring entirely are borrowing against their future senior pipeline. This would change if AI review becomes reliable enough to replace human code review."
- Discussion question: "If you hired a junior dev in the last year, what did their first month look like compared with five years ago?"

### Bad
- "{Named CEO} is a fraud and their AI is a scam." Personal attack, unsupported.
- "Developers are finished. Learn plumbing." Not defensible, outrage bait.

## Quality checklist
- [ ] Both sides have sourced evidence
- [ ] Opposing view steelmanned
- [ ] Position includes a falsifier
- [ ] No personal attacks, false scandals, or political partisanship
- [ ] `sensitive` flag set correctly
- [ ] Discussion question invites experience

## Output structure
```json
{
  "question": "", "main_argument": "", "opposing_argument": "",
  "supporting_evidence": [{"claim": "", "url": ""}], "counter_evidence": [{"claim": "", "url": ""}],
  "nuance": "", "defensible_position": "", "would_change_if": "",
  "discussion_question": "", "sensitive": false, "sensitivity_reasons": []
}
```
