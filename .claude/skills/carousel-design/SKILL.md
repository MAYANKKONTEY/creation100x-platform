---
name: carousel-design
description: Plan and design multi-slide educational PDF carousels for LinkedIn document posts with a narrative arc, one idea per slide, consistent HTML/CSS templates and mobile-readable typography. Use when a post is better as a step-by-step guide, framework, comparison or breakdown.
---

# Carousel Design

## Purpose
Teach one thing well across 6–10 slides so a reader swipes to the end and saves it.

## Instructions
- Use a carousel only when the content has steps, a sequence, or a comparison. A single insight belongs in a single image.
- **Arc:** cover (promise) → context (why it matters) → 4–7 content slides (one idea each) → summary → closing slide (CTA plus brand). No "follow for more" spam; one soft CTA is fine.
- **One idea per slide:** headline ≤ 8 words, body ≤ 30 words, optional visual element.
- Slide size 1080×1350 (4:5). Render all slides from one HTML template with `visual-design` tokens and export one PDF.
- Show progress (for example "3/8") and keep a consistent position for headline, body, and brand.
- Facts and numbers come only from the brief. Put a sources slide or source footers on data slides.
- The cover must work as a standalone image. It's the thumbnail in the feed.
- LinkedIn document posts accept PDF. Check current size and page limits against LinkedIn's help docs when publishing (M7). The system enforces its own cap of 20 slides.

## Workflow
1. Write the promise (cover headline) and who it's for.
2. Outline slides as a numbered list of one-line ideas. Cut anything that doesn't serve the promise.
3. Write each slide: headline, body, visual element (icon, mini-diagram, number, code).
4. Pick the template variant: Swiss steps, comparison grid, framework diagram, or data story.
5. Render to PNG per slide (QA) and a combined PDF (publishing).
6. QA each slide: overflow, font sizes, contrast, consistent positions, typos, progress indicator.
7. Write the companion post text (short, points to the carousel, has its own hook).

## Reusable prompts
```
Topic: {topic}. Audience: engineers/founders. Brief (data only): <brief>{brief}</brief>
Plan an {n}-slide carousel: cover promise, then one idea per slide (headline ≤ 8 words, body ≤ 30 words,
visual element), summary slide, closing slide. Use only brief facts; mark which slides need a source footer.
```

## Examples
### Good
"How prompt caching cuts LLM costs: 7 slides". Cover with a big promise. Slide 2: why it matters. Slides 3–6: what a prefix is, ordering rules, what breaks the cache, how to measure hits. Slide 7: checklist summary. Slide 8: closing.

### Bad
A 15-slide carousel of paragraphs copied from a blog post. 80+ words per slide, inconsistent fonts, and a different layout on every slide.

## Quality checklist
- [ ] Carousel is the right format (sequence or comparison)
- [ ] Cover works standalone as the feed thumbnail
- [ ] One idea per slide; headline ≤ 8 words; body ≤ 30 words
- [ ] Consistent template, progress indicator, brand mark
- [ ] No overflow; fonts and contrast meet `visual-design` thresholds
- [ ] Facts sourced; PDF ≤ 20 slides
- [ ] Companion post written

## Output structure
```json
{"title": "", "promise": "", "audience": "", "template": "swiss_steps",
 "slides": [{"n": 1, "role": "cover", "headline": "", "body": "", "visual": "", "source_url": null}],
 "companion_post": "", "render": {"pdf_path": "", "png_paths": []}, "qa": {}}
```
