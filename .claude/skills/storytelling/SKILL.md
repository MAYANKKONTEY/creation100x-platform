---
name: storytelling
description: Structure story-driven LinkedIn posts (founder lessons, build in public, personal experience, case narratives) using only owner-supplied or publicly sourced facts. Use when a post's format is storytelling, founder lessons or build in public.
---

# Storytelling

## Purpose
Make an idea memorable by putting it in a concrete moment. Stories carry the insight; they never replace evidence and are never invented.

## Instructions
- **Source of story facts:** (a) the owner's notes or answers, (b) a public, sourced story about a company or person, written in the third person. Nothing else.
- If no owner story is available, either write a third-person story from sources or produce a template with `[OWNER INPUT NEEDED: …]` prompts and route it to review.
- Structure: scene → tension → turn → lesson. Start in the moment, not with background.
- Use concrete details (time, tool, number, quote) only when they are supplied or sourced.
- One story, one lesson. Cut subplots.
- End with a lesson the reader can apply, phrased as a rule or question.
- Avoid the formula "I was rejected 100 times… now I'm a CEO." Avoid fake vulnerability and humble-brags.

## Workflow
1. Identify the lesson in one sentence.
2. Collect story facts and label each `owner` or `sourced:url`.
3. Pick the scene: the most specific moment of tension.
4. Draft scene (1–2 lines) → tension → turn → lesson.
5. Remove every sentence that does not move the story or the lesson.
6. Check that every detail has a label. Unlabelled details are deleted.

## Reusable prompts
**Interview the owner (for build in public / founder lessons)**
```
To write this story I need from you:
1. What were you trying to do? (one sentence)
2. What went wrong or surprised you? Any number you can share?
3. What did you change afterwards?
4. What would you tell someone about to do the same thing?
```
**Draft**
```
Lesson: {lesson}
Facts (each labelled owner or sourced): {facts}
Write a {length}-character LinkedIn story: scene, tension, turn, lesson.
Use only the labelled facts. No invented dialogue or numbers.
```

## Examples
### Good (third person, sourced)
```
In 2008, Airbnb's founders were selling cereal boxes to stay afloat.
[source]
The boxes weren't the business. They were proof the founders would
do unscalable things to survive.
Lesson: early on, the scrappy thing that keeps you alive is a signal,
not a distraction.
```

### Bad
```
Last Tuesday a Fortune 500 CEO DMed me in tears asking how I built
my AI empire...
```
An invented scene with an unverifiable, self-aggrandising detail.

## Quality checklist
- [ ] Every detail labelled owner or sourced
- [ ] Starts in a scene, not background
- [ ] One lesson, stated plainly
- [ ] No invented dialogue, numbers, or emotions attributed to real people
- [ ] Missing owner facts marked `[OWNER INPUT NEEDED]`

## Output structure
```json
{"lesson": "", "facts": [{"text": "", "origin": "owner|sourced", "url": ""}],
 "story": {"scene": "", "tension": "", "turn": "", "lesson": ""},
 "owner_input_needed": []}
```
