---
title: "Company"
type: state
updated:
---

# Company

What this business is. Slow-moving — changes a few times a year, not weekly.
Everything else in this repo is judged against this page, so keep it honest
rather than aspirational.

## What it is

_One paragraph: what the business does and why it exists._

## What I sell

_Offers, pricing, and the rough economics of each (what it costs to produce,
what it earns). If there's no revenue yet, say what the path to it is._

## Who it's for

_The audience/customer. Specific enough that "is this for them?" is answerable._

## Constraints

_The real limits: hours per week, cash, skills, anything non-negotiable.
This is what makes advice realistic instead of generic._

## Metrics that matter

The single source of truth for what the numbers mean. Anything reported in
[dashboard.md](dashboard.md) is defined here — including department numbers.
A unit's `direction.md` in [departments/](departments/README.md) names which
metrics it owns; it never redefines them. One definition, one place.

`Dept` is the unit that owns the number (`company`, `marketing/ads`,
`marketing/content`, `sales`). It's what lets the dashboard group rows without
anyone maintaining a second list.

| Metric | Dept | Definition | Where it comes from | Healthy | Watch | Bad |
|---|---|---|---|---|---|---|
| _e.g. subscribers_ | _company_ | _net subs_ | _`automations/` channel report_ | _+X/mo_ | _flat_ | _declining_ |
| _e.g. cost per purchase_ | _marketing/ads_ | _spend ÷ purchases_ | _`automations/scripts/marketing/`_ | _< £X_ | _£X–Y_ | _> £Y_ |

## Stack

_Tools and accounts, and where each one's data lives — so automations know
what's wirable._
