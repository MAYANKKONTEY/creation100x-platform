---
name: linkedin-seo
description: Optimise LinkedIn posts, articles, newsletters and the owner's profile for relevant search discovery with natural keyword placement, search-intent matching, topic clusters, profile alignment and a ranking-awareness checklist. Use when producing the SEO report for a post, article SEO packages, or profile recommendations.
---

# LinkedIn SEO

## Purpose
Help the right people find the owner's content and profile through LinkedIn search and external search engines, through clarity and relevance rather than tricks.

## Instructions
- Nobody outside LinkedIn knows its ranking formula. Never claim first-page rankings, guaranteed reach, or "algorithm hacks". Everything here is good practice and a heuristic.
- **Keywords:** one primary keyword (the phrase someone would search), 2–4 secondary keywords, and 3–5 related phrases. Identify the search intent: learn, compare, solve, or follow news.
- **Placement:** the primary keyword (or a close variant) appears naturally in the first two lines. Secondary keywords appear once each where they fit. Density ceiling: no single keyword more than 3 times in a 1,300-character post.
- **Hashtags:** 0–3, only when they name a real topic community. Never a block of 10.
- **Descriptive wording:** use specific nouns ("Claude prompt caching") over vague ones ("this AI trick").
- **Articles/newsletters:** SEO title (≤ 60 characters, keyword near the front), description (≤ 155 characters), H2 structure that matches likely questions, and internal links to the owner's related articles where supported.
- **Profile alignment:** headline, About, and Skills should use the same core topics the content covers. Recommend changes but never write claims about the owner's experience. Leave placeholders for those.
- **Topic clusters:** map each post to one of the content pillars and track coverage so the profile builds topical authority.

## Ranking-awareness checklist (heuristic, 10 dimensions)
1. Identity relevance: is the topic within the owner's stated expertise?
2. Content relevance: is the subject clear in the first two lines?
3. Audience interests: does it match what the target audience searches and discusses?
4. Freshness: is the news angle current, or is it evergreen by design?
5. Originality: is there a perspective beyond restating the news?
6. Information value: will a reader learn something specific?
7. Professional credibility: are claims sourced and the tone expert?
8. Meaningful conversations: does the CTA invite substantive replies?
9. Audience response: does it resemble past posts that drew real comments (from analytics, when available)?
10. Topic consistency: does it fit an existing pillar or cluster?

## Workflow
1. Identify search intent and the primary keyword from the brief's topic.
2. Generate secondary keywords and related phrases.
3. Check placement, density, and hashtags in the draft.
4. Score the 10 checklist items pass / warn / fail with a reason.
5. Write recommendations as concrete edits.
6. Monthly: produce a profile alignment report against the published topic clusters.

## Reusable prompts
```
Post draft: <post>{post}</post>  Topic: {topic}  Pillar: {pillar}
Return: search_intent, primary_keyword, secondary_keywords[], related_phrases[],
placement checks, density warnings, hashtag suggestions (0-3, with reason),
ranking_awareness checklist (10 items: pass/warn/fail + reason), recommended_edits[].
Do not promise rankings or reach.
```

## Examples
### Good
Primary keyword "AI coding agents" appears in line 1. Secondary keywords "code review" and "developer productivity" each appear once. One hashtag (#SoftwareEngineering).

### Bad
"#AI #ArtificialIntelligence #AIagents #AItools #Tech #Innovation #Future #Startups #Growth #Leadership". Keyword "AI" used 14 times. Promises to "beat the algorithm".

## Quality checklist
- [ ] Primary keyword in first two lines, naturally
- [ ] No keyword > 3 uses; no hashtag block
- [ ] Intent identified and matched by the content
- [ ] All 10 ranking-awareness items assessed
- [ ] No promises of ranking or reach

## Output structure
```json
{"search_intent": "learn", "primary_keyword": "", "secondary_keywords": [], "related_phrases": [],
 "checks": {"keyword_in_opening": true, "max_keyword_count": 0, "hashtags": []},
 "ranking_awareness": [{"dimension": "identity_relevance", "result": "pass", "reason": ""}],
 "recommended_edits": [""], "pillar": "", "cluster": "",
 "article_seo": {"title": "", "description": "", "headings": []}}
```
