---
title: "Sales — Experiments"
type: append-only
unit: sales
---

# Sales — experiments

Append-only. Newest at the bottom. **Never edit a past entry** — except to fill
in `Result` and `Verdict` at the read date.

Format:

```
## [YYYY-MM-DD] Title

**Status:** running | concluded | killed
**Hypothesis:** what you believe, and why.
**Setup:** what changed — offer, price, script, follow-up sequence, page.
**Cost:** money + hours.
**Read on:** YYYY-MM-DD — and for sales, say the sample size you need too.
  A conversion test read on 12 visitors tells you nothing.
**Result:** _(filled at read — real numbers)_
**Verdict:** worked | failed | inconclusive — and what changed because of it.
**Led to:** _(link to a decisions.md entry, or "nothing")_
```

Quick recall:
- open experiments — `grep -n "Status:. running" departments/sales/experiments.md`

---

_No experiments logged yet._
