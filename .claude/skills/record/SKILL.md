---
name: record
description: Record something that happened in the business: a decision, a change to something live, an experiment, or a fact. Classifies it first, then files it correctly with the right fields. Triggers on "record", "log this", "we decided", "I changed", "I launched".
---

# Record

Something happened. **Classify it before writing anything**, and say which kind you think it is:

| It is... | Test | File it as |
|---|---|---|
| **A decision** | A choice with a consequence you could be wrong about | `decision add` (title, decided, rationale, **expect**, **review**) + a `decision` log entry |
| **A change** | A live edit: price, funnel, creative, budget, targeting | `log add --type change --title "..." --body "what, from, to, when"` so a later report can compare either side |
| **An action or experiment** | Launched to learn, no choice made yet | `log add --type capture` that says what it should settle and when you'll look |
| **A fact** | Something now true about the business | Update in place: `company set`, `dept update`, or a `doc update`; log it if it changes direction |

Don't promote an intention to a decision. "I'm thinking of..." is an open call (`call add`), not a decision.

## For a decision

Ask, in this order, one at a time if they're missing:
1. What exactly was decided? (one sentence)
2. Why, and what number or fact prompted it?
3. **What should be true by the review date if this was right?** Push for something checkable, ideally a number.
4. **When will you check?** A real date. If they can't name one, the decision can't be judged: say so.

Then `python3 brain.py decision add --title "..." --decided "..." --expect "..." --review YYYY-MM-DD --rationale "..." --dept ...`,
update goals or bets if it moves a target (`bet update`, `goal update`) and say what moved, and log it.
If it supersedes an earlier decision, pass `--supersedes ID`. Past decisions are append-only: never try to edit them, supersede them.

Keep it brief. Confirm what you filed in two lines.
