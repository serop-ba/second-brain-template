---
title: "Decisions"
type: append-only
---

# Decisions

Append-only. Never edit a past entry — if a decision is reversed, write a new
one that links back to it.

Every entry carries a **prediction** and a **review date**. That's the point:
a decision log without predictions is an archive, one with them is how this
system gets smarter. The weekly loop surfaces entries whose review date has
passed.

Format:

```
## [YYYY-MM-DD] Title

**Decided:** what we're doing.
**Why:** the reasoning, and what data/goal prompted it.
**Expect:** what should be true if this was right.
**Review on:** YYYY-MM-DD
**Outcome:** _(filled in at review — right, wrong, or mixed, and what it taught)_
```

Quick recall: `grep -n "Review on:" decisions.md`

---

_No decisions logged yet._
