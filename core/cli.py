"""The `brain` command line: the one way Claude (or you) reads and changes the business.

  python3 brain.py context            what Claude should read first
  python3 brain.py <group> <verb>     see --help on any group

Every write is recorded in the change history with who did it and why (--reason).
Run with --json for machine-readable output. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import backup
import db
import metrics
import packs
import refresh
import registry
import seed
import store
import views
from store import Error

JSON = False


def out(data, text: str | None = None) -> None:
    if JSON or text is None:
        print(json.dumps(data, indent=1, default=str, ensure_ascii=False))
    else:
        print(text)


def table(rows: list[dict], cols: list[str], empty: str = "none") -> str:
    if not rows:
        return empty
    cells = [[str("" if r.get(c) is None else r.get(c)).replace("\n", " ")[:70] for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    line = lambda vals: "  ".join(v.ljust(widths[i]) for i, v in enumerate(vals)).rstrip()
    return "\n".join([line(cols), line(["-" * w for w in widths]), *(line(r) for r in cells)])


def text_of(args, field: str = "text", required: bool = True) -> str | None:
    """Long text from --<field>, --file, or '-' (stdin)."""
    value = getattr(args, field, None)
    if getattr(args, "file", None):
        return Path(args.file).read_text()
    if value == "-":
        return sys.stdin.read()
    if value is None and required:
        raise Error(f"give --{field} (or --file PATH, or --{field} - to read stdin)")
    return value


def since(value: str | None) -> str | None:
    if not value:
        return None
    if value.endswith("d") and value[:-1].isdigit():
        return (date.today() - timedelta(days=int(value[:-1]))).isoformat()
    return store.check_date(value, "--since")


def why(args) -> str | None:
    return getattr(args, "reason", None)


def _lines(value: str | None) -> str | None:
    return value.replace("\\n", "\n") if value else value


# --------------------------------------------------------------------------- handlers

def h_context(a):
    print(views.status_text(full=a.full))


def h_company(a):
    if a.verb == "show":
        p = store.profile_get()
        out(p, "\n".join(f"{k}: {v}" for k, v in p.items()) or "no company facts yet. Add with: company set name \"...\"")
    elif a.verb == "set":
        store.profile_set(a.key, a.value, why(a)); out({"ok": True}, f"set {a.key}")
    else:
        store.profile_unset(a.key, why(a)); out({"ok": True}, f"removed {a.key}")


def h_dept(a):
    if a.verb == "list":
        rows = store.dept_list()
        out(rows, table(rows, ["slug", "name", "owner", "hours", "briefed_at"], "no departments yet. Add with: dept add NAME"))
    elif a.verb == "show":
        d = store.dept_get(a.ref)
        lines = [f"{d['name']} ({d['slug']}), lead {d['owner'] or '-'}, {d['hours'] or '?'} h/wk", f"Owns: {d['owns'] or '-'}", d["intro"]]
        if d["brief"]:
            lines += ["", f"BRIEF ({d['briefed_at']}):", d["brief"]]
        for s in d["sections"]:
            lines += ["", f"## {s['title']}  [{s['slug']}]", s["body"] or "(empty)"]
        mine = [m for m in metrics.metric_list(with_points=False) if m["department"] == d["slug"]]
        lines += ["", "Metrics: " + (", ".join(f"{m['name']} {m['now'] if m['now'] is not None else '-'} ({m['verdict']})" for m in mine) or "none")]
        out(d, "\n".join(lines))
    elif a.verb == "add":
        d = store.dept_add(a.name, slug=a.slug, reason=why(a), owner=a.owner, hours=a.hours, owns=a.owns, intro=a.intro, sections=not a.no_sections)
        out(d, f"added department {d['slug']}")
    elif a.verb == "update":
        d = store.dept_update(a.ref, why(a), **{k: v for k, v in dict(name=a.name, owner=a.owner, hours=a.hours, owns=a.owns, intro=a.intro).items() if v is not None})
        out(d, f"updated {d['slug']}")
    elif a.verb == "rm":
        store.dept_remove(a.ref, why(a)); out({"ok": True}, f"removed {a.ref} (its notes and metrics are kept, unassigned)")
    else:
        store.dept_brief(a.ref, text_of(a), why(a)); out({"ok": True}, f"brief saved for {a.ref}")


def h_doc(a):
    v = a.verb
    if v == "list":
        rows = store.doc_list(a.kind, a.dept, a.q)
        out(rows, table(rows, ["slug", "kind", "title", "department", "tags", "ingested", "updated_at"], "no documents"))
    elif v == "get":
        d = store.doc_get(a.ref)
        out(d, f"# {d['title']}   [{d['kind']}] {d['slug']}  dept={d['department'] or '-'} tags={d['tags'] or '-'} updated {d['updated_at']}\n\n{d['body']}")
    elif v == "add":
        d = store.doc_add(a.title, text_of(a, "body", False) or "", a.kind, a.dept, a.tags or "", a.slug, a.source_ref or "", why(a))
        out(d, f"added {d['kind']} {d['slug']}")
    elif v == "import":
        p = Path(a.path)
        d = store.doc_add(a.title or p.stem.replace("-", " ").replace("_", " ").title(), p.read_text(), a.kind, a.dept, a.tags or "", None, str(p), why(a))
        out(d, f"imported {p.name} as {d['kind']} {d['slug']}")
    elif v == "update":
        f = {k: val for k, val in dict(title=a.title, body=text_of(a, "body", False), kind=a.kind, department=a.dept, tags=a.tags).items() if val is not None}
        d = store.doc_update(a.ref, why(a), **f)
        out(d, f"updated {d['slug']}")
    elif v == "rm":
        store.doc_remove(a.ref, why(a)); out({"ok": True}, f"removed {a.ref} (restorable from history)")
    elif v == "ingest":
        d = store.doc_ingest(a.ref, why(a)); out(d, f"marked {a.ref} as ingested")
    elif v == "search":
        rows = store.doc_list(q=a.q)
        out(rows, table(rows, ["slug", "kind", "title"], "no match"))
    else:
        d = store.doc_get(a.ref)
        rows = store.history("documents", d["id"])
        out(rows, table([{"change": r["id"], "when": r["ts"], "who": r["actor"], "what": r["action"], "why": r["reason"]} for r in rows], ["change", "when", "who", "what", "why"], "no history"))


def h_north_star(a):
    store.north_star_set(a.text, a.detail or "", why(a)); out({"ok": True}, "north star set")


def h_goal(a):
    if a.verb == "list":
        g = store.goals_get()
        out(g, f"North star: {g['north_star']['text'] if g['north_star'] else '(not set)'}\n{g['year_label']}:\n" + "\n".join(f"  #{x['id']} {x['text']}" for x in g["year"]))
    elif a.verb == "add":
        i = store.year_add(a.text, a.detail or "", why(a)); out({"id": i}, f"added year goal #{i}")
    elif a.verb == "update":
        store.goal_update(a.id, why(a), **{k: v for k, v in dict(text=a.text, detail=a.detail).items() if v is not None}); out({"ok": True}, "updated")
    else:
        store.goal_remove(a.id, why(a)); out({"ok": True}, "removed")


def h_bet(a):
    if a.verb == "list":
        rows = store.bet_list()
        out(rows, table(rows, ["n", "title", "department", "status", "success"], "no bets yet. Add with: bet add TITLE --success ..."))
    elif a.verb == "add":
        b = store.bet_add(a.title, why(a), department=a.dept, why=a.why_, success=a.success, status=a.status, status_note=a.note, next_steps=_lines(a.next))
        out(b, f"added Bet {b['n']}")
    elif a.verb == "update":
        f = dict(title=a.title, department=a.dept, why=a.why_, success=a.success, status=a.status, status_note=a.note, next_steps=_lines(a.next))
        b = store.bet_update(a.n, why(a), **{k: v for k, v in f.items() if v is not None})
        out(b, f"updated Bet {a.n}")
    else:
        store.bet_remove(a.n, why(a)); out({"ok": True}, f"removed Bet {a.n}")


def h_call(a):
    if a.verb == "list":
        rows = store.call_list(not a.all)
        out(rows, table(rows, ["id", "question", "context"], "no open calls"))
    elif a.verb == "add":
        i = store.call_add(a.question, a.context or "", why(a)); out({"id": i}, f"added open call #{i}")
    elif a.verb == "resolve":
        store.call_resolve(a.id, a.text or "", why(a)); out({"ok": True}, f"resolved #{a.id}. If it was a real choice, also: decision add ...")
    else:
        store.call_remove(a.id, why(a)); out({"ok": True}, "removed")


def h_task(a):
    v = a.verb
    if v in ("list", None):
        s = store.task_snapshot()
        out(s, "\n".join([f"This week {s['week']}", "Goals:"] + [f"  #{i['id']} [{'x' if i['done'] else ' '}] {i['text']}" + (f" (Bet {i['bet']})" if i["bet"] else " (no bet)")
                                                              + (f" [carried {i['carried']}w]" if i["carried"] else "") for i in s["goals"]]
                         + [f"Today {s['today']}:"] + [f"  #{i['id']} [ ] {i['text']}" + (f" (Bet {i['bet']})" if i["bet"] else " (no bet)")
                                                      + (f" [from {i['from_day']}]" if i["from_day"] else "") for i in s["today_items"]]
                         + ["Done this week:"] + [f"  {i['done_at'][:10]} {i['text']}" for i in s["done"]]))
    elif v == "add":
        i = store.task_add(a.kind, a.text, a.bet, why(a)); out({"id": i}, f"added #{i}" + ("" if a.bet or "#bet" in a.text else " (serves no bet: say so, or pass --bet N)"))
    elif v == "edit":
        store.task_update(a.id, a.text, None if a.no_bet else a.bet, why(a)); out({"ok": True}, f"updated #{a.id}")
    elif v == "done":
        store.task_done(a.id, why(a)); out({"ok": True}, f"done #{a.id}")
    elif v == "undo":
        store.task_undo(a.id, why(a)); out({"ok": True}, f"reopened #{a.id}")
    elif v == "rm":
        store.task_remove(a.id, why(a)); out({"ok": True}, f"removed #{a.id}")
    else:
        print(store.task_week_summary(a.week))


def h_decision(a):
    v = a.verb
    if v == "list":
        rows = store.decision_list(a.due)
        out(rows, table([{**r, "status": "DUE" if r["due"] else ("open" if r["pending"] else "reviewed")} for r in rows], ["id", "date", "title", "review_on", "status"], "no decisions"))
    elif v == "add":
        i = store.decision_add(a.title, a.decided, a.expect, a.review, a.why_, a.dept, a.supersedes, None, why(a)); out({"id": i}, f"logged decision #{i}. Now also: log add --type decision ...")
    elif v == "outcome":
        store.decision_outcome(a.id, a.text, why(a)); out({"ok": True}, f"outcome saved for #{a.id}")
    elif v == "update":
        store.decision_update(a.id, why(a), **{k: val for k, val in dict(title=a.title, decided=a.decided, why=a.why_, expect=a.expect, review_on=a.review).items() if val is not None}); out({"ok": True}, "updated")
    else:
        store.decision_remove(a.id, why(a)); out({"ok": True}, "removed")


def h_log(a):
    if a.verb == "list":
        rows = store.log_list(a.n, a.type, since(a.since))
        out(rows, "\n".join(f"{r['date']} {r['type']} | {r['title']}" + (f"\n    {r['body']}" if a.body and r["body"] else "") for r in rows) or "no entries")
    else:
        i = store.log_add(a.type, a.title, text_of(a, "body", False) or "", a.dept, a.date, why(a)); out({"id": i}, f"logged #{i}")


def h_inbox(a):
    if a.verb == "list":
        rows = store.inbox_list(not a.all)
        out(rows, table(rows, ["id", "text", "filed_to"], "inbox is empty"))
    elif a.verb == "add":
        i = store.inbox_add(a.text, why(a)); out({"id": i}, f"captured #{i}")
    elif a.verb == "file":
        store.inbox_file(a.id, a.to or "", why(a)); out({"ok": True}, f"filed #{a.id}")
    else:
        store.inbox_remove(a.id, why(a)); out({"ok": True}, "removed")


def h_metric(a):
    v = a.verb
    if v == "list":
        rows = metrics.metric_list(with_points=False)
        out(rows, table([{**r, "now": "-" if r["now"] is None else f"{r['now']:g}"} for r in rows], ["key", "name", "department", "now", "verdict", "as_of", "source"],
                        "no metrics yet. Add with: metric add KEY --name ... --dept ..."))
    elif v == "show":
        m = metrics.metric_get(a.key)
        out(m, f"{m['name']} [{m['key']}] {m['department'] or '-'}  source={m['source']}\n{m['definition']}\nhealthy {m['healthy'] or '-'} | watch {m['watch'] or '-'} | bad {m['bad'] or '-'}\n"
               f"now {m['now']} ({m['verdict']}) as of {m['as_of']}\n" + "\n".join(f"  {p['as_of']}  {p['value']:g}  [{p['origin']}]" for p in m["points"][-30:]))
    elif v == "add":
        m = metrics.metric_add(a.key, a.name, why(a), department=a.dept, definition=a.definition, unit=a.unit, source=a.source, healthy=a.healthy, watch=a.watch, bad=a.bad)
        out(m, f"added metric {m['key']}. Give it a value: metric set {m['key']} <number>")
    elif v == "update":
        f = dict(name=a.name, department=a.dept, definition=a.definition, unit=a.unit, source=a.source, healthy=a.healthy, watch=a.watch, bad=a.bad)
        m = metrics.metric_update(a.key, why(a), **{k: val for k, val in f.items() if val is not None}); out(m, f"updated {a.key}")
    elif v == "rm":
        metrics.metric_remove(a.key, why(a)); out({"ok": True}, f"removed {a.key} and its history")
    elif v == "set":
        metrics.point_set(a.key, a.value, a.date, a.note or "", reason=why(a)); out({"ok": True}, f"{a.key} = {a.value} on {a.date or db.today()}")
    else:
        metrics.point_delete(a.key, a.date, why(a)); out({"ok": True}, f"deleted {a.key} on {a.date}")


def h_refresh(a):
    status = refresh.refresh(a.automation)
    sys.exit(0 if status["ok"] else 1)


def h_automation(a):
    if a.verb == "list":
        rows = [{"name": x["name"], "label": x["label"], "env_missing": ", ".join(registry.missing_env(x)) or "-", "pulls": len(x["pull"])} for x in registry.automations()]
        cat = [{**c, "installed": "yes" if c["installed"] else "no"} for c in registry.catalog()]
        out({"installed": rows, "catalog": cat}, "INSTALLED\n" + table(rows, ["name", "label", "env_missing", "pulls"], "none") + "\n\nCATALOG (install with: automation install NAME)\n" + table(cat, ["name", "label", "installed", "description"]))
    elif a.verb == "install":
        r = packs.install_automation(a.name); out(r, f"installed {a.name}. Metrics created: {', '.join(r['metrics_created']) or 'none'}\nNext: {r['next']}")
    else:
        packs.remove_automation(a.name); out({"ok": True}, f"removed automations/{a.name}")


def h_profile(a):
    if a.verb == "list":
        rows = registry.profiles(); out(rows, table(rows, ["name", "label", "description"], "none"))
    else:
        r = packs.apply_profile(a.name); out(r, f"applied {a.name}: departments {', '.join(r['departments']) or 'none new'}; metrics {', '.join(r['metrics']) or 'none new'}")


def h_history(a):
    rows = store.changes(a.n, a.entity, a.id, a.actor)
    out(rows, table([{"change": r["id"], "when": r["ts"], "who": r["actor"], "what": f"{r['action']} {r['entity']}", "detail": r["summary"], "why": r["reason"]} for r in rows],
                    ["change", "when", "who", "what", "detail", "why"], "no changes"))


def h_revert(a):
    msg = store.revert(a.change, why(a)); out({"ok": True, "message": msg}, msg)


def h_search(a):
    rows = store.search(a.q)
    out(rows, table(rows, ["kind", "id", "title", "snippet"], "no match"))


def h_backup(a):
    out({"path": str(backup.backup())}, f"backup written: {backup.backups()[0]}")


def h_export(a):
    p = backup.export(a.out); out({"path": str(p)}, f"exported to {p}")


def h_restore(a):
    safety = backup.restore(a.file); out({"ok": True}, f"restored from {a.file} (the previous database was saved as {safety})")


def h_demo(a):
    if a.verb == "load":
        r = seed.load(a.force); out(r, f"demo data loaded ({r['rows']} rows). Remove it any time: python3 brain.py demo clear")
    elif a.verb == "clear":
        if seed.is_demo():
            backup.backup("before-demo-clear")
        r = seed.clear(); out(r, f"demo cleared: {r['removed']} rows removed" + (f", {r['kept']} you edited were kept" if r["kept"] else ""))
    else:
        out({"demo": views.demo_active()}, "demo data is loaded" if views.demo_active() else "no demo data")


def h_serve(a):
    import server
    server.main(a.port, not a.no_open)


# --------------------------------------------------------------------------- parser

def build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--reason", help="why you're making this change (kept in the change history)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output")
    common.add_argument("--reason", default=argparse.SUPPRESS, help="why you're making this change (kept in the change history)")
    sub = p.add_subparsers(dest="group", required=True, metavar="group")

    def grp(name, fn, help_):
        g = sub.add_parser(name, help=help_)
        g.set_defaults(fn=fn)
        return g, g.add_subparsers(dest="verb", required=True, metavar="verb")

    def verb(s, name, *args, **opts):
        v = s.add_parser(name, parents=[common], help=opts.pop("help", None))
        for spec in args:
            flags, kw = spec[0], spec[1] if len(spec) > 1 else {}
            v.add_argument(*(flags if isinstance(flags, tuple) else (flags,)), **kw)
        return v

    TEXT = ("--text", {"help": "the text, or - for stdin"})
    FILE = ("--file", {"help": "read the text from this file"})

    c = sub.add_parser("context", aliases=["status"], parents=[common], help="what to read first: company, bets, week, numbers, what needs attention")
    c.add_argument("--full", action="store_true", help="add briefs, open decisions, recent log and the library index")
    c.set_defaults(fn=h_context)

    g, s = grp("company", h_company, "company facts (name, stage, hours, runway...)")
    verb(s, "show"); verb(s, "set", ("key",), ("value",)); verb(s, "unset", ("key",))

    g, s = grp("dept", h_dept, "departments and their pages")
    verb(s, "list"); verb(s, "show", ("ref",))
    verb(s, "add", ("name",), ("--slug",), ("--owner", {"default": ""}), ("--hours", {"default": ""}), ("--owns", {"default": ""}), ("--intro", {"default": ""}), ("--no-sections", {"action": "store_true"}))
    verb(s, "update", ("ref",), ("--name",), ("--owner",), ("--hours",), ("--owns",), ("--intro",))
    verb(s, "rm", ("ref",)); verb(s, "brief", ("ref",), TEXT, FILE)

    g, s = grp("doc", h_doc, "notes, sources, playbooks and department page sections")
    verb(s, "list", ("--kind",), ("--dept",), ("-q",)); verb(s, "get", ("ref",)); verb(s, "search", ("q",)); verb(s, "history", ("ref",))
    verb(s, "add", ("title",), ("--kind", {"default": "note"}), ("--dept",), ("--tags",), ("--slug",), ("--source-ref",), ("--body",), FILE)
    verb(s, "import", ("path",), ("--title",), ("--kind", {"default": "source"}), ("--dept",), ("--tags",))
    verb(s, "update", ("ref",), ("--title",), ("--kind",), ("--dept",), ("--tags",), ("--body",), FILE)
    verb(s, "rm", ("ref",)); verb(s, "ingest", ("ref",))

    g = sub.add_parser("north-star", parents=[common], help="set the north star")
    g.add_argument("text"); g.add_argument("--detail"); g.set_defaults(fn=h_north_star, verb="set")

    g, s = grp("goal", h_goal, "this year's goals")
    verb(s, "list"); verb(s, "add", ("text",), ("--detail",)); verb(s, "update", ("id", {"type": int}), ("--text",), ("--detail",)); verb(s, "rm", ("id", {"type": int}))

    g, s = grp("bet", h_bet, "this quarter's bets")
    verb(s, "list")
    for name in ("add", "update"):
        v = verb(s, name, ("title",) if name == "add" else ("n", {"type": int}), ("--dept",), ("--rationale", {"dest": "why_"}), ("--success",), ("--status",), ("--note",), ("--next", {"help": "next steps, one per line"}))
        if name == "update":
            v.add_argument("--title", dest="title")
    verb(s, "rm", ("n", {"type": int}))

    g, s = grp("call", h_call, "open calls: questions not decided yet")
    verb(s, "list", ("--all", {"action": "store_true"})); verb(s, "add", ("question",), ("--context",))
    verb(s, "resolve", ("id", {"type": int}), ("--text",)); verb(s, "rm", ("id", {"type": int}))

    g, s = grp("task", h_task, "this week's goals and today's priorities")
    g.set_defaults(verb=None)
    s.required = False
    verb(s, "list"); verb(s, "add", ("kind", {"choices": ["goal", "today"]}), ("text",), ("--bet", {"type": int}))
    verb(s, "edit", ("id", {"type": int}), ("text",), ("--bet", {"type": int}), ("--no-bet", {"action": "store_true"}))
    for n in ("done", "undo", "rm"):
        verb(s, n, ("id", {"type": int}))
    verb(s, "week", ("week", {"nargs": "?"}))

    g, s = grp("decision", h_decision, "decisions, each with a prediction and a review date")
    verb(s, "list", ("--due", {"action": "store_true"}))
    verb(s, "add", ("--title", {"required": True}), ("--decided", {"required": True}), ("--expect", {"required": True}), ("--review", {"required": True, "help": "YYYY-MM-DD"}),
         ("--rationale", {"dest": "why_", "default": ""}), ("--dept",), ("--supersedes", {"type": int}))
    verb(s, "outcome", ("id", {"type": int}), ("text",))
    verb(s, "update", ("id", {"type": int}), ("--title",), ("--decided",), ("--rationale", {"dest": "why_"}), ("--expect",), ("--review",))
    verb(s, "rm", ("id", {"type": int}))

    g, s = grp("log", h_log, "the append-only timeline")
    verb(s, "list", ("--type",), ("--since",), ("-n", {"type": int, "default": 15}), ("--body", {"action": "store_true"}))
    verb(s, "add", ("--type", {"required": True}), ("--title", {"required": True}), ("--body",), FILE, ("--dept",), ("--date",))

    g, s = grp("inbox", h_inbox, "quick capture")
    verb(s, "list", ("--all", {"action": "store_true"})); verb(s, "add", ("text",)); verb(s, "file", ("id", {"type": int}), ("--to",)); verb(s, "rm", ("id", {"type": int}))

    g, s = grp("metric", h_metric, "numbers: definitions, thresholds and daily values")
    verb(s, "list"); verb(s, "show", ("key",)); verb(s, "rm", ("key",))
    for name in ("add", "update"):
        v = verb(s, name, ("key",), ("--dept",), ("--definition",), ("--unit",), ("--source",), ("--healthy",), ("--watch",), ("--bad",))
        v.add_argument("--name", required=(name == "add"))
    verb(s, "set", ("key",), ("value",), ("--date",), ("--note",)); verb(s, "delete-point", ("key",), ("date",))

    r = sub.add_parser("refresh", parents=[common], help="run every automation's pull and record the numbers")
    r.add_argument("automation", nargs="?"); r.set_defaults(fn=h_refresh)

    g, s = grp("automation", h_automation, "installed automations and the use-case catalog")
    verb(s, "list"); verb(s, "install", ("name",)); verb(s, "remove", ("name",))

    g, s = grp("profile", h_profile, "starter profiles (departments + metrics) from the catalog")
    verb(s, "list"); verb(s, "apply", ("name",))

    h = sub.add_parser("history", parents=[common], help="the change history: who changed what, when and why")
    h.add_argument("--entity"); h.add_argument("--id", type=int); h.add_argument("--actor"); h.add_argument("-n", type=int, default=30); h.set_defaults(fn=h_history)
    rv = sub.add_parser("revert", parents=[common], help="undo one recorded change (recorded too)"); rv.add_argument("change", type=int); rv.set_defaults(fn=h_revert)
    se = sub.add_parser("search", parents=[common], help="search documents, decisions, the log and metrics"); se.add_argument("q"); se.set_defaults(fn=h_search)

    sub.add_parser("backup", parents=[common], help="a consistent copy of the database").set_defaults(fn=h_backup)
    e = sub.add_parser("export", parents=[common], help="everything as JSON"); e.add_argument("--out"); e.set_defaults(fn=h_export)
    rs = sub.add_parser("restore", parents=[common], help="replace the database with a backup"); rs.add_argument("file"); rs.set_defaults(fn=h_restore)

    g, s = grp("demo", h_demo, "demo data you can wipe in one command")
    verb(s, "load", ("--force", {"action": "store_true"})); verb(s, "clear"); verb(s, "status")

    sv = sub.add_parser("serve", parents=[common], help="open the console (http://127.0.0.1:8765)")
    sv.add_argument("--port", type=int, default=8765); sv.add_argument("--no-open", action="store_true"); sv.set_defaults(fn=h_serve)
    return p


def main(argv: list[str] | None = None) -> None:
    global JSON
    args = build().parse_args(argv)
    JSON = args.json
    try:
        args.fn(args)
    except Error as exc:
        sys.exit(f"error: {exc}")
    except sqlite3.IntegrityError as exc:
        sys.exit(f"error: refused by the database: {exc}")
    except sqlite3.DatabaseError as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
