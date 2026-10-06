---
name: init
description: Set up this brain for a real business. Clears the demo data, interviews the founder (about ten minutes), then files company facts, departments, metrics with thresholds, goals, bets and working rules into the database. Run once, first. Triggers on "init", "set up my brain", "get started", or when `context` says the brain is empty or shows DEMO DATA.
---

# Init

The brain ships with demo data (or empty). Your job: **interview the founder, then file the real business**, so every other
skill has something true to work from. Read `CLAUDE.md` first if it isn't in context.

## Before you start

1. Run `python3 brain.py context`. If it says `DEMO DATA`, tell the user the demo will be removed and run `python3 brain.py demo clear` (it makes a backup first and removes only what the demo created).
2. If real data already exists, don't overwrite: say so and ask whether to update specific parts instead.
3. Say, in two lines: you'll ask about the business, the numbers and this quarter, about ten minutes, and nothing is written until the end.

## The interview

Conversational, in rounds, two or three questions per message. React to answers: follow up on vague ones, push back on weak ones.
That is the job, not politeness.

**Round 1: the business.** What does it do and for whom? What do you sell, at what price? (If nothing yet, what's the path to revenue?)
Stage: idea, first revenue, growing, established?

**Round 2: reality.** How many hours a week do you really have? Runway or cash situation, roughly? What is most likely to kill this in the next year?
What would make you stop (the kill condition, with a number and a date)? Don't skip this round: constraints are what separate useful advice from generic advice.

**Round 3: how it runs.** Which functions are actually running (marketing, sales, delivery, product, customer, finance...)? Name only real work, with the hours each gets.
If their business matches a starter profile (`python3 brain.py profile list`: creator, service, saas, ecommerce) offer to apply it as a starting set of departments and metrics, then adapt.
For each channel running: what's already been tried and stopped? (Highest-value answer, nobody volunteers it. Ask directly and file it in that department's "What we've learned".)

**Round 4: the numbers.** Which 3 to 5 numbers tell you whether this is working? For each: where does it come from, what's healthy, what's watch, what's bad, in the founder's own thresholds?
Challenge any vanity metric: if it can rise while the business gets worse, ask what they'd track instead. If they can't name a threshold, leave the band blank rather than inventing one.

**Round 5: direction.** Where should this be in 1 to 3 years (north star)? What would make this year a success (2 to 4 goals)? What are you betting this quarter (max three, each with a number that says it worked, each carried by a department)?
What are you stuck deciding right now (open calls)?

**Round 6: how I should work with you.** Tone, brand voice, things I should always or never do. (This becomes the `working-rules` document.)

## Then file it

Only after the interview. Use `--reason "init"` on writes.

1. **Company**: `company set name "..."`, `tagline`, `stage`, `hours_per_week`, `runway`, `kill_condition`, `offers`, `who_its_for`, `positioning`, `constraints`. Their words, not yours. Also `company set planning_year 2026` (the current year).
2. **Departments**: `dept add NAME --owner ... --hours ... --owns "..." --intro "what it's trying to do"`. Only functions with real work. Then fill each page's sections with what they told you: `doc update <slug>/strategy --body "..."`, `<slug>/whats-running`, `<slug>/what-weve-learned`, `<slug>/open-questions`.
3. **Metrics**: `metric add KEY --name ... --dept ... --unit ... --definition "exactly what is counted" --healthy ... --watch ... --bad ...`. Then log today's value for each one they know: `metric set KEY VALUE`. Don't invent values.
4. **Direction**: `north-star "..."`, `goal add "..."` for each year goal, `bet add "..." --dept ... --success "..." --rationale "..." --status "not started" --next "..."` (max three), `call add "..."` for each open call.
5. **This week**: `task add goal "..." --bet N` for 3 to 5 outcomes, and at most three `task add today`.
6. **Working rules**: `doc add "Working rules" --kind playbook --tags rules --body "..."` from round 6 (slug becomes `working-rules`).
7. **Log**: `log add --type init --title "Brain initialised" --body "<one paragraph: what was set up>"`.

## Wrap up

- Run `python3 brain.py context` and show it. Name the one thing most likely to rot first (usually: nobody logs the numbers) and how they'll feed it.
- List which metrics could be pulled automatically instead of by hand (`python3 brain.py automation list` shows the use-case packs: Stripe, YouTube, Meta Ads CSV, CSV import) and offer `/connect` as the next step. Don't build anything now.
- Tell them to run `python3 brain.py serve` to open the console.

## Don't

- Don't ask all the questions at once. Don't accept "TBD" for the north star or the kill condition without noting it as an open call.
- Don't scaffold departments for work that isn't happening: an empty department reads as coverage when it's neglect.
- Don't invent thresholds, numbers or goals. Don't edit the database any way except `brain.py`.
