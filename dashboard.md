---
title: "Dashboard"
type: derived
updated:
---

# Dashboard

Current state — the one page to open. **Derived, not authored:** I regenerate
this during the weekly loop from automation output,
[goals.md](goals.md) and each unit in [departments/](departments/README.md).
Don't hand-edit it; edit the source and let it be rebuilt.

There is exactly one dashboard. Departments get a section here, not a page of
their own — a dashboard you have to visit four of is four dashboards.

_Not yet generated. Run `/init`, then the weekly loop._

## Numbers

Company-level. Every metric defined in [company.md](company.md).

| Metric | Now | Last week | Target | Verdict |
|---|---|---|---|---|

## Bets

_Each bet from [goals.md](goals.md) with on-track / at-risk / stalled, and the
department carrying it._

## Marketing

_Direction in one line, from [departments/marketing/direction.md](departments/marketing/direction.md)._

### Ads

| Metric | Now | Last week | Target | Verdict |
|---|---|---|---|---|

**Running experiments** — _name, day N, read on DATE, current read._

### Content

| Metric | Now | Last week | Target | Verdict |
|---|---|---|---|---|

**Running experiments** — _name, day N, read on DATE, current read._

## Sales

| Metric | Now | Last week | Target | Verdict |
|---|---|---|---|---|

**Running experiments** — _name, day N, read on DATE, current read._

## Needs attention

_Anomalies, stalled bets, experiments past their read date with no result,
decisions past their review date, stale pages, units with no activity._

## Recent

_Last few entries from [log.md](log.md)._

## Data freshness

| Source | Last pulled | Script |
|---|---|---|

_A number with no pull date is a number you can't trust. If a script didn't
run, the row says so — it never gets a stale value copied forward._
