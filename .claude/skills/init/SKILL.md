---
name: init
description: Set up a fresh second brain — interviews the founder about their business, then fills in company.md, goals.md, the automation config, and the working rules. Run this once, first. Triggers on "init", "set up my second brain", "get started", or when company.md is still template text.
---

# Init

This repo ships empty on purpose. Your job is to fill it in by **interviewing
the founder**, then writing the four things that make everything else work.

Read `CLAUDE.md` first if it isn't in context.

## Before you start

Check it hasn't already been run:

```bash
grep -q "_One paragraph" company.md && echo "still template" || echo "already filled"
```

If it's already filled, say so and ask whether to update rather than overwrite.

Then say, in two lines: you'll ask about the business, the numbers, and this
quarter — about ten minutes — and nothing gets written until the end.

## The interview

Ask **conversationally, in four rounds**, not as a questionnaire. Two or three
questions per message. React to answers — follow up when something is vague,
and push back when something is weak. That's the job, not politeness.

**Round 1 — the business**
- What does the business do, and who is it for?
- What do you sell, at what price? If nothing yet, what's the path to revenue?
- What stage: idea, first revenue, growing, or established?

**Round 2 — reality**
- How many hours a week do you actually have for this?
- What's the runway or cash situation, roughly?
- What's the one thing most likely to kill this in the next year?

Don't skip round 2. Constraints are what separate useful advice from generic
advice, and founders under-report them.

**Round 3 — the numbers**
- Which 3–5 numbers actually tell you if this is working?
- For each: where does it come from, and what value would be healthy vs bad?
- Challenge any vanity metric — if a number can go up while the business gets
  worse, say so and ask what they'd track instead.

**Round 4 — direction**
- Where should this be in 1–3 years? (north star)
- What would make *this year* a success?
- What are you betting this quarter — max three, each with a number attached?

Then ask if they want anything added to the working rules: tone, brand voice,
things you should always or never do.

## Then write

Only after the interview. Fill in, in this order:

1. **`company.md`** — every section, in their words not yours. The metrics
   table needs real thresholds; if they couldn't give one, write `TBD` rather
   than inventing a number.
2. **`goals.md`** — north star, this year, and the quarter's bets with
   success numbers, status `not started`, and 2–3 next steps each.
3. **`CLAUDE.md`** — append anything from the working-rules question to the
   *Rules for how I work* section. Don't touch the rest.
4. **Automations** — `automations/` ships empty. Don't build anything now.
   Note in the log which of their metrics could be pulled automatically and
   which are manual, and mention it in the wrap-up as a later step.
5. **`log.md`** — append `## [YYYY-MM-DD] init | Second brain initialized`
   and one paragraph on what was set up.

Leave `dashboard.md`, `decisions.md`, `inbox.md`, and `wiki/` alone. They
fill themselves as the system runs.

## Don't

- Don't write anything before the interview is done.
- Don't invent numbers, thresholds, or goals they didn't give you. `TBD` is a
  valid answer; a fabricated metric is not.
- Don't accept a bet with no number. Push until there's one, or mark it
  `unmeasured` and flag it.
- Don't leave template placeholder text sitting next to real content.

## After

Three lines, no more:
- What got set up.
- The weakest thing you heard — the vanity metric, the bet that doesn't ladder
  to the north star, the constraint they're ignoring. Say it plainly.
- What to do next: add a source to `raw/` and run `/ingest`, or fill in
  `automations/.env` and run the weekly loop.
