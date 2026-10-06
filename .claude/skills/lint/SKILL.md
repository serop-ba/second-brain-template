---
name: lint
description: Health-check the brain: contradictions, stale claims, bets with no activity, decisions past review, metrics with no data or no bands, departments that read as coverage but are neglect. Triggers on "lint the brain", "health check", "what's stale".
---

# Lint

Start with `python3 brain.py context --full`, then `doc list` and `search` as needed. Report, don't fix silently:

1. **Contradictions and stale claims**: documents that disagree with each other or with newer log entries and numbers. Quote both, with their dates.
2. **Orphans and gaps**: documents nothing links to (`[[slug]]`); concepts that appear in several documents but have no note of their own; sources never ingested (`doc list --kind source`).
3. **Bets**: any with no weekly goal or log entry this month; any whose success number has no metric behind it.
4. **Decisions**: past review with no outcome (`decision list --due`); open decisions whose expectation can't be checked from any metric.
5. **Numbers**: metrics with no value in 14 days, no definition, or no bands; the same concept defined twice.
6. **Departments**: hours near zero but pages claiming things are running; no metrics and no bets; an inbox older than a week.
7. **History**: `history -n 50`, anything odd (a bulk delete, many reverts) worth asking about.

End with the three most valuable fixes, in order. Offer to do them. Log the lint: `log add --type lint --title "Lint" --body "<findings in a few lines>"`.
