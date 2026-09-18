---
title: "Departments"
type: state
updated:
---

# Departments

The company pages at the root answer *how is the business doing*. This folder
answers *what are we actually trying, and did it work* — one folder per area of
work you're spending real time on.

It is deliberately the same mechanism as the root, one level down. No new
concepts to learn.

## The shape

Every unit — a department, or a channel inside one — is a folder with at most
two files:

| File | Kind | Rule |
|---|---|---|
| `direction.md` | **state** | Always current. Edited in place. Where this unit is headed, what's proven, what's dead. |
| `experiments.md` | **events** | Append-only. Every test you ran, with a hypothesis and a read date. Never edit a past entry. |

**`experiments.md` lives where the work happens.** A department with channels
(marketing → ads, content) puts experiments in the channels — the department
keeps only `direction.md`. A department without channels (sales) keeps its own.

```
departments/
  sales/
    direction.md
    experiments.md
  marketing/
    direction.md          ← strategy across channels
    ads/
      direction.md
      experiments.md      ← the actual tests
    content/
      direction.md
      experiments.md
```

## Experiment vs decision

They look similar and they are not.

- An **experiment** is a test you run to find something out. It has a
  *hypothesis* and a *read-on date*. It lives here.
- A **decision** is a commitment you make. It has an *expectation* and a
  *review-on date*. It lives in [../decisions.md](../decisions.md).

Experiments feed decisions. A test that works should usually produce a decision
entry; the experiment entry links to it. Don't log a decision for "we're going
to try X" — that's an experiment.

## Where the numbers are defined

Nowhere in here. Every metric is defined once in
[../company.md](../company.md)'s metrics table, tagged with the department that
owns it. A unit's `direction.md` names which metrics it owns; it never
redefines them. This is the rule that stops three folders each having their own
quiet definition of CPA.

Automation output for a unit lands in `Output/analytics/<department>/` and is
pulled by scripts in `automations/scripts/<department>/`.

## Adding one

Ask Claude: *"add a department for support"* or *"add an email channel under
marketing"*. It copies the two-file shape, registers the unit in
[../CLAUDE.md](../CLAUDE.md) and adds a dashboard section.

Adding a department is a real decision. The value of this system is that it's
small, and an empty folder is worse than no folder — it looks like coverage.
Only add one when there's work happening in it *this month*. If a channel has
had no experiment in a quarter, fold it back into its department's
`direction.md` under "what's dead" and delete the folder.
