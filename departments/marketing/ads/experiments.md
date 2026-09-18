---
title: "Ads — Experiments"
type: append-only
unit: marketing/ads
---

# Ads — experiments

Append-only. Newest at the bottom. **Never edit a past entry** — except to fill
in `Result` and `Verdict` when the read date arrives, which is the whole point
of the format.

Every entry has a **hypothesis** and a **read-on date**. An experiment with no
read date never gets judged; it just quietly becomes "what we do". The weekly
loop surfaces any entry past its read date with an empty `Result`.

Format:

```
## [YYYY-MM-DD] Title

**Status:** running | concluded | killed
**Hypothesis:** what you believe, and why you believe it.
**Setup:** what actually went live — creative, audience, placement, offer, budget.
**Cost:** money spent + hours spent.
**Read on:** YYYY-MM-DD — when there's enough data to judge, decided up front.
**Result:** _(filled at read — the actual numbers, not a feeling)_
**Verdict:** worked | failed | inconclusive — and what changed because of it.
**Led to:** _(link to a decisions.md entry, or "nothing")_
```

Quick recall:
- open experiments — `grep -n "Status:. running" departments/marketing/ads/experiments.md`
- due for a read — `grep -n "Read on:" departments/marketing/ads/experiments.md`

---

_No experiments logged yet._
