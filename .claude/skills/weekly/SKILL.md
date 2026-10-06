---
name: weekly
description: Run the weekly loop with the founder: empty the inbox, pull the numbers, check the bets, review decisions due, brief departments, and write the weekly log entry. Triggers on "weekly", "run the weekly loop", or when `context` says the weekly loop hasn't run in over a week.
---

# Weekly loop

Follow the **Weekly loop** section of `CLAUDE.md` exactly, with the founder in the conversation. Start from `python3 brain.py context --full`.

Sequence:

1. **Inbox to zero.** `inbox list`. For each item, decide and do: a note (`doc add`), a task (`task add ... --bet N`), a decision (`decision add`), a metric value (`metric set`), a source (`doc add --kind source`). Then `inbox file ID --to "<where>"`. Ask only when an item is genuinely ambiguous. Also run `doc sweep` to pull anything in `drop/` into the library as sources, then ingest them (see the ingest skill).
2. **Numbers.** `python3 brain.py refresh`. On a missing key or failure, stop and say what to fill in. For hand-logged metrics that are stale (context lists them), ask for the value and `metric set` it. Never fabricate.
3. **Bets.** For each bet say on track / at risk / stalled with the evidence, and write it back: `bet update N --status "..." --note "..."`. A bet with nothing scheduled this week is a finding. A weekly goal carried twice is a stalled bet or a goal nobody believes in: say which.
4. **Decisions due.** `decision list --due`: ask what actually happened, record it with `decision outcome ID "..."`. This is how the system learns; don't skip it.
5. **Departments.** For each: update What's running / What we've learned / Open questions where stale, and rewrite the brief. Pull in what the log and numbers say; name the department that is blocking another.
6. **Close.** `task week` for the summary, then `log add --type weekly --title "Week NN: <headline>" --body "Moved: ... Didn't: ... Next: ..."`.
7. **Offer** a decision for anything that needs a real choice, and a plan for next week (`task add goal ...`, at most five).

Be direct. Lead with the one thing that matters most this week, then the evidence. If nothing moved, say so.
