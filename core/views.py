"""Read models: the one-screen status Claude loads at the start of a session, and the state the console renders.

Nothing here writes. Numbers and verdicts come from metrics.py; this only arranges them. Stdlib only.
"""

from __future__ import annotations

from datetime import date

import db
import metrics
import refresh
import registry
import store


def attention() -> list[str]:
    """What needs a human or Claude now, most important first."""
    out = []
    today = db.today()
    due = store.decision_list(due_only=True)
    if due:
        out.append(f"{len(due)} decision(s) past review with no outcome: " + "; ".join(f"#{d['id']} {d['title']}" for d in due))
    last = store.last_log("weekly")
    if last is None:
        out.append("no weekly entry yet: run the weekly loop")
    elif (date.fromisoformat(today) - date.fromisoformat(last)).days > 7:
        out.append(f"weekly loop last ran {last}")
    inbox = store.inbox_list()
    if inbox:
        out.append(f"{len(inbox)} item(s) in the inbox")
    ms = metrics.metric_list(with_points=False)
    nodata = [m["name"] for m in ms if m["now"] is None]
    if nodata:
        out.append("no data for: " + ", ".join(nodata))
    stale = [m["name"] for m in ms if m["as_of"] and (date.fromisoformat(today) - date.fromisoformat(m["as_of"])).days > 14]
    if stale:
        out.append("not updated in 14+ days: " + ", ".join(stale))
    snap = store.task_snapshot()
    open_items = [i for i in snap["goals"] + snap["today_items"] if not i["done"]]
    for b in store.bet_list():
        if b["status"].lower() not in ("done", "won", "dropped") and not any(i["bet"] == b["n"] for i in open_items):
            out.append(f"Bet {b['n']} ({b['title']}) has nothing scheduled this week")
    stuck = [g for g in snap["goals"] if not g["done"] and g["carried"] > 1]
    if stuck:
        out.append(f"{len(stuck)} weekly goal(s) carried 2+ weeks: cut or commit")
    unbriefed = [d["name"] for d in store.dept_list() if not d["briefed_at"]]
    if unbriefed and len(unbriefed) == len(store.dept_list()):
        out.append("no department has been briefed yet")
    return out


def demo_active() -> bool:
    if db.meta_get("demo") != "1":
        return False
    with db.read() as con:
        return bool(con.execute("SELECT 1 FROM demo_rows LIMIT 1").fetchone())


def company_name() -> str:
    return store.profile_get().get("name", "Brain OS")


def status_text(full: bool = False) -> str:
    """What Claude should read first. `full` adds department briefs, recent log, decisions and the document index."""
    prof = store.profile_get()
    goals = store.goals_get()
    L = [f"BRAIN STATUS {db.today()} (week {store.iso_week()})" + ("   [DEMO DATA: run /init to replace it]" if demo_active() else "")]
    try:
        rules = store.doc_get("working-rules")["body"].strip()
    except store.Error:
        rules = ""
    if rules:
        L += ["", "Working rules (library: working-rules):", rules[:1800], ""]
    if not prof:
        L += ["", "The brain is empty. Run /init to set it up (a short interview, then Claude files your business)."]
    L.append(f"Company: {prof.get('name', '(unnamed)')}" + (f" - {prof['tagline']}" if prof.get("tagline") else ""))
    extra = [f"{k}: {v}" for k, v in prof.items() if k not in ("name", "tagline", "planning_year")]
    L += [f"  {x}" for x in extra]
    star = goals["north_star"]
    L.append(f"North star: {star['text'] if star else '(not set)'}")
    if goals["year"]:
        L.append(f"{goals['year_label']} goals: " + " | ".join(g["text"] for g in goals["year"]))
    bets = store.bet_list()
    L += ["", "Bets:"] + ([f"  Bet {b['n']} [{b['status']}] {b['title']}" + (f" ({b['department']})" if b["department"] else "")
                         + (f" - wins if: {b['success']}" if b["success"] else "") for b in bets] or ["  none yet"])
    snap = store.task_snapshot()
    L += ["", f"This week ({snap['week']}):"]
    for i in snap["goals"]:
        L.append(f"  goal #{i['id']} [{'x' if i['done'] else ' '}] {i['text']}" + (f" (Bet {i['bet']})" if i["bet"] else " (no bet)") + (f" carried {i['carried']}w" if i["carried"] else ""))
    for i in snap["today_items"]:
        L.append(f"  today #{i['id']} [ ] {i['text']}" + (f" (Bet {i['bet']})" if i["bet"] else " (no bet)"))
    if not snap["goals"] and not snap["today_items"]:
        L.append("  nothing set")
    ms = metrics.metric_list(with_points=False)
    L += ["", "Numbers:"]
    for m in ms:
        now = "-" if m["now"] is None else f"{m['now']:g}{(' ' + m['unit']) if m['unit'] else ''}"
        chg = "" if m["delta"] is None else f" ({m['delta']:+g} since {m['prev']:g})"
        L.append(f"  {m['name']} [{m['key']}] ({m['department'] or 'no dept'}): {now}{chg} - {m['verdict']}" + (f" as of {m['as_of']}" if m["as_of"] else ""))
    if not ms:
        L.append("  none defined. Add with: metric add")
    depts = store.dept_list()
    L += ["", "Departments:"] + [f"  {d['slug']}: {d['name']}, lead {d['owner'] or '-'}, {d['hours'] or '?'} h/wk, "
                                 f"{'briefed ' + d['briefed_at'] if d['briefed_at'] else 'not briefed'}" for d in depts]
    if not depts:
        L.append("  none yet. Add with: dept add")
    todo = attention()
    L += ["", "Needs attention:"] + ([f"  - {t}" for t in todo] or ["  nothing"])
    if full:
        for d in depts:
            if d["brief"]:
                L += ["", f"Brief: {d['name']}", d["brief"]]
        L += ["", "Open decisions (no outcome yet):"]
        L += [f"  #{d['id']} {d['title']} (review {d['review_on']}): expect {d['expect']}" for d in store.decision_list() if d["pending"]] or ["  none"]
        L += ["", "Open calls:"] + ([f"  #{c['id']} {c['question']}" for c in store.call_list()] or ["  none"])
        L += ["", "Recent log:"] + [f"  {e['date']} {e['type']} | {e['title']}" for e in store.log_list(10)]
        L += ["", "Library:"] + [f"  [{d['kind']}] {d['slug']}: {d['title']}" for d in store.doc_list() if d["kind"] != "section"][:60]
    return "\n".join(L)


def state() -> dict:
    import jobs  # late: jobs imports this module's siblings
    prof = store.profile_get()
    ms = metrics.metric_list()
    depts = store.dept_list()
    docs = store.doc_list()
    for d in depts:
        d["sections"] = [x for x in store.doc_list(kind="section", dept=d["id"], with_body=True)]
        d["sections"].sort(key=lambda s: (s["position"], s["id"]))
    log = store.log_list(12)
    return {
        "today": db.today(),
        "company": prof.get("name", "Brain OS"),
        "profile": prof,
        "demo": demo_active(),
        "departments": depts,
        "documents": docs,
        "goals": store.goals_get(),
        "bets": store.bet_list(),
        "calls": store.call_list(),
        "tasks": store.task_snapshot(),
        "decisions": store.decision_list(),
        "metrics": ms,
        "log": {"recent": log, "last_weekly": store.last_log("weekly"), "count": len(store.log_list(100000))},
        "inbox": store.inbox_list(),
        "attention": attention(),
        "changes": store.changes(40),
        "refresh": {"last": refresh.last_status(), "at": db.meta_get("refresh_at")},
        "jobs": jobs.catalogue(),
        "catalog": registry.catalog(),
        "profiles": registry.profiles(),
    }
