"""Every read and write of the business, in one place.

The CLI, the console and Claude's skills all call these functions, so there is
exactly one set of rules. Writes run inside db.write(), which makes the audit
triggers record who changed what and why. Stdlib only.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import db


class Error(ValueError):
    """A request the brain refuses, with a message that says what to do instead."""


# --------------------------------------------------------------------------- helpers

LOG_TYPE = re.compile(r"^[a-z][a-z-]{1,24}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_SECTIONS = ["Strategy", "What's running", "What we've learned", "Open questions"]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("'", "")).strip("-") or "untitled"


def check_date(value: str, label: str = "date") -> str:
    value = (value or "").strip()
    if not DATE.match(value):
        raise Error(f"{label} must be YYYY-MM-DD, got {value!r}")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise Error(f"{label} {value!r} is not a real date") from None
    return value


def _pick(fields: dict, allowed: list[str]) -> dict:
    unknown = [k for k in fields if k not in allowed]
    if unknown:
        raise Error(f"unknown field(s): {', '.join(unknown)}. Allowed: {', '.join(allowed)}")
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items() if v is not None}


def _insert(con, table: str, data: dict) -> int:
    cols = list(data)
    cur = con.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", list(data.values()))
    return cur.lastrowid


def _update(con, table: str, row_id: int, data: dict) -> None:
    if data:
        con.execute(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in data)} WHERE id = ?", [*data.values(), row_id])


def _all(con, sql: str, *params) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params)]


def _one(con, sql: str, *params) -> dict | None:
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def dept_id(con, ref) -> int | None:
    """A department by id, slug or name. None for blank."""
    if ref in (None, "", 0):
        return None
    if isinstance(ref, int) or str(ref).isdigit():
        row = con.execute("SELECT id FROM departments WHERE id = ?", (int(ref),)).fetchone()
    else:
        row = con.execute("SELECT id FROM departments WHERE slug = ? OR lower(name) = lower(?)", (str(ref), str(ref))).fetchone()
    if not row:
        names = ", ".join(r["slug"] for r in con.execute("SELECT slug FROM departments ORDER BY position, id"))
        raise Error(f"no department {ref!r}. Existing: {names or 'none yet, add one with: dept add'}")
    return row["id"]


def _unique_slug(con, table: str, base: str) -> str:
    slug, n = base, 2
    while con.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


# --------------------------------------------------------------------------- company profile

def profile_get() -> dict:
    with db.read() as con:
        return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM profile ORDER BY id")}


def profile_set(key: str, value: str, reason: str | None = None) -> None:
    key = slugify(key).replace("-", "_")
    if not str(value).strip():
        raise Error("empty value (use profile_unset to remove a fact)")
    with db.write(reason) as con:
        con.execute(
            "INSERT INTO profile (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, str(value).strip(), db.now()))


def profile_unset(key: str, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM profile WHERE key = ?", (key,)).rowcount:
            raise Error(f"no profile fact {key!r}")


# --------------------------------------------------------------------------- departments

DEPT_FIELDS = ["name", "owner", "hours", "owns", "intro"]


def dept_list() -> list[dict]:
    with db.read() as con:
        return _all(con, "SELECT * FROM departments ORDER BY position, id")


def dept_get(ref) -> dict:
    with db.read() as con:
        row = _one(con, "SELECT * FROM departments WHERE id = ?", dept_id(con, ref))
        row["sections"] = _all(con, "SELECT * FROM documents WHERE department_id = ? AND kind = 'section' ORDER BY position, id", row["id"])
    return row


def dept_add(name: str, slug: str | None = None, reason: str | None = None, sections: bool = True, **fields) -> dict:
    name = name.strip()
    if not name:
        raise Error("a department needs a name")
    data = _pick(fields, ["owner", "hours", "owns", "intro"])
    with db.write(reason) as con:
        slug = slugify(slug or name)
        if con.execute("SELECT 1 FROM departments WHERE slug = ?", (slug,)).fetchone():
            raise Error(f"department {slug!r} already exists")
        pos = con.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM departments").fetchone()[0]
        did = _insert(con, "departments", {"slug": slug, "name": name, "position": pos, "created_at": db.now(), "updated_at": db.now(), **data})
        if sections:
            for i, title in enumerate(DEFAULT_SECTIONS):
                _insert(con, "documents", {"slug": f"{slug}/{slugify(title)}", "title": title, "kind": "section", "department_id": did,
                                           "position": i, "created_at": db.now(), "updated_at": db.now()})
    return dept_get(did)


def dept_update(ref, reason: str | None = None, **fields) -> dict:
    data = _pick(fields, DEPT_FIELDS + ["position"])
    with db.write(reason) as con:
        did = dept_id(con, ref)
        _update(con, "departments", did, {**data, "updated_at": db.now()})
    return dept_get(did)


def dept_remove(ref, reason: str | None = None) -> None:
    """Removing a department keeps its notes and metrics (they become unassigned) but deletes its page sections."""
    with db.write(reason) as con:
        did = dept_id(con, ref)
        con.execute("DELETE FROM documents WHERE department_id = ? AND kind = 'section'", (did,))
        con.execute("DELETE FROM departments WHERE id = ?", (did,))


def dept_brief(ref, text: str, reason: str | None = None) -> None:
    """The department lead's current brief (Claude writes it; the page shows it)."""
    if not text.strip():
        raise Error("empty brief")
    with db.write(reason) as con:
        did = dept_id(con, ref)
        _update(con, "departments", did, {"brief": text.strip(), "briefed_at": db.today(), "updated_at": db.now()})


# --------------------------------------------------------------------------- documents

DOC_KINDS = ["note", "source", "playbook", "section"]
DOC_FIELDS = ["title", "body", "kind", "department", "tags", "ingested", "source_ref", "position"]


def _doc_row(con, ref) -> dict:
    if isinstance(ref, int) or str(ref).isdigit():
        row = _one(con, "SELECT * FROM documents WHERE id = ?", int(ref))
    else:
        row = _one(con, "SELECT * FROM documents WHERE slug = ?", str(ref))
    if not row:
        raise Error(f"no document {ref!r}. Find it with: doc search <words>")
    return row


def _tags(value) -> str:
    items = value if isinstance(value, list) else str(value).split(",")
    return ",".join(sorted({t.strip().lower() for t in items if t.strip()}))


def doc_list(kind: str | None = None, dept=None, q: str | None = None, with_body: bool = False) -> list[dict]:
    where, params = [], []
    with db.read() as con:
        if kind:
            where.append("d.kind = ?"); params.append(kind)
        if dept:
            where.append("d.department_id = ?"); params.append(dept_id(con, dept))
        if q:
            where.append("(d.title LIKE ? OR d.body LIKE ? OR d.tags LIKE ?)"); params += [f"%{q}%"] * 3
        cols = "d.*" if with_body else "d.id, d.slug, d.title, d.kind, d.department_id, d.tags, d.ingested, d.source_ref, d.position, d.created_at, d.updated_at, length(d.body) AS size"
        return _all(con, f"SELECT {cols}, p.slug AS department FROM documents d LEFT JOIN departments p ON p.id = d.department_id"
                         f"{' WHERE ' + ' AND '.join(where) if where else ''} ORDER BY d.kind = 'section', d.updated_at DESC", *params)


def doc_get(ref) -> dict:
    with db.read() as con:
        row = _doc_row(con, ref)
        row["department"] = (_one(con, "SELECT slug FROM departments WHERE id = ?", row["department_id"]) or {}).get("slug")
    return row


def doc_add(title: str, body: str = "", kind: str = "note", department=None, tags="", slug: str | None = None,
            source_ref: str = "", reason: str | None = None) -> dict:
    if kind not in DOC_KINDS:
        raise Error(f"kind must be one of {', '.join(DOC_KINDS)}")
    if not title.strip():
        raise Error("a document needs a title")
    with db.write(reason) as con:
        did = dept_id(con, department)
        base = slugify(slug or title)
        if kind == "section" and did:
            base = f"{con.execute('SELECT slug FROM departments WHERE id = ?', (did,)).fetchone()['slug']}/{base}"
        pos = con.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM documents WHERE department_id IS ? AND kind = ?", (did, kind)).fetchone()[0]
        new = _insert(con, "documents", {"slug": _unique_slug(con, "documents", base), "title": title.strip(), "kind": kind, "department_id": did,
                                         "tags": _tags(tags), "body": body.strip(), "position": pos, "source_ref": source_ref,
                                         "created_at": db.now(), "updated_at": db.now()})
    return doc_get(new)


def doc_update(ref, reason: str | None = None, **fields) -> dict:
    data = _pick(fields, DOC_FIELDS)
    if "kind" in data and data["kind"] not in DOC_KINDS:
        raise Error(f"kind must be one of {', '.join(DOC_KINDS)}")
    with db.write(reason) as con:
        row = _doc_row(con, ref)
        if "department" in data:
            data["department_id"] = dept_id(con, data.pop("department"))
        if "tags" in data:
            data["tags"] = _tags(data["tags"])
        if "title" in data and not data["title"]:
            raise Error("a document needs a title")
        _update(con, "documents", row["id"], {**data, "updated_at": db.now()})
    return doc_get(row["id"])


def doc_remove(ref, reason: str | None = None) -> None:
    with db.write(reason) as con:
        con.execute("DELETE FROM documents WHERE id = ?", (_doc_row(con, ref)["id"],))


def doc_ingest(ref, reason: str | None = None) -> dict:
    """Mark a source as processed: the one flag a source ever changes."""
    return doc_update(ref, reason, ingested=1)


# --------------------------------------------------------------------------- direction: north star, goals, bets, open calls

def goals_get() -> dict:
    with db.read() as con:
        goals = _all(con, "SELECT * FROM goals ORDER BY position, id")
    star = next((g for g in goals if g["level"] == "north_star"), None)
    return {"north_star": star, "year": [g for g in goals if g["level"] == "year"],
            "year_label": profile_get().get("planning_year") or str(date.today().year)}


def north_star_set(text: str, detail: str = "", reason: str | None = None) -> None:
    if not text.strip():
        raise Error("the north star can't be empty")
    with db.write(reason) as con:
        cur = _one(con, "SELECT id FROM goals WHERE level = 'north_star'")
        if cur:
            _update(con, "goals", cur["id"], {"text": text.strip(), "detail": detail.strip(), "updated_at": db.now()})
        else:
            _insert(con, "goals", {"level": "north_star", "text": text.strip(), "detail": detail.strip(), "created_at": db.now(), "updated_at": db.now()})


def year_add(text: str, detail: str = "", reason: str | None = None) -> int:
    if not text.strip():
        raise Error("empty goal")
    with db.write(reason) as con:
        pos = con.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM goals WHERE level = 'year'").fetchone()[0]
        return _insert(con, "goals", {"level": "year", "text": text.strip(), "detail": detail.strip(), "position": pos,
                                      "created_at": db.now(), "updated_at": db.now()})


def goal_update(goal_id: int, reason: str | None = None, **fields) -> None:
    data = _pick(fields, ["text", "detail", "position"])
    with db.write(reason) as con:
        if not con.execute("SELECT 1 FROM goals WHERE id = ?", (goal_id,)).fetchone():
            raise Error(f"no goal {goal_id}")
        _update(con, "goals", goal_id, {**data, "updated_at": db.now()})


def goal_remove(goal_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM goals WHERE id = ?", (goal_id,)).rowcount:
            raise Error(f"no goal {goal_id}")


BET_FIELDS = ["title", "department", "why", "success", "status", "status_note", "next_steps"]


def bet_list() -> list[dict]:
    with db.read() as con:
        rows = _all(con, "SELECT b.*, d.slug AS department FROM bets b LEFT JOIN departments d ON d.id = b.department_id ORDER BY b.n")
    for r in rows:
        r["next"] = [s.strip() for s in r["next_steps"].splitlines() if s.strip()]
    return rows


def bet_add(title: str, reason: str | None = None, **fields) -> dict:
    if not title.strip():
        raise Error("a bet needs a title")
    data = _pick(fields, [f for f in BET_FIELDS if f != "title"])
    with db.write(reason) as con:
        data["department_id"] = dept_id(con, data.pop("department", None))
        n = con.execute("SELECT COALESCE(MAX(n), 0) + 1 FROM bets").fetchone()[0]
        _insert(con, "bets", {"n": n, "title": title.strip(), "created_at": db.now(), "updated_at": db.now(), **data})
    return next(b for b in bet_list() if b["n"] == n)


def bet_update(n: int, reason: str | None = None, **fields) -> dict:
    data = _pick(fields, BET_FIELDS)
    with db.write(reason) as con:
        row = _one(con, "SELECT id FROM bets WHERE n = ?", n)
        if not row:
            raise Error(f"no bet {n}")
        if "department" in data:
            data["department_id"] = dept_id(con, data.pop("department"))
        _update(con, "bets", row["id"], {**data, "updated_at": db.now()})
    return next(b for b in bet_list() if b["n"] == n)


def bet_remove(n: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM bets WHERE n = ?", (n,)).rowcount:
            raise Error(f"no bet {n}")
        con.execute("UPDATE items SET bet = NULL WHERE bet = ?", (n,))


def call_list(open_only: bool = True) -> list[dict]:
    with db.read() as con:
        return _all(con, f"SELECT * FROM open_calls{' WHERE resolved_at IS NULL' if open_only else ''} ORDER BY id")


def call_add(question: str, context: str = "", reason: str | None = None) -> int:
    if not question.strip():
        raise Error("empty question")
    with db.write(reason) as con:
        return _insert(con, "open_calls", {"question": question.strip(), "context": context.strip(), "created_at": db.now()})


def call_update(call_id: int, reason: str | None = None, **fields) -> None:
    data = _pick(fields, ["question", "context"])
    with db.write(reason) as con:
        if not con.execute("SELECT 1 FROM open_calls WHERE id = ?", (call_id,)).fetchone():
            raise Error(f"no open call {call_id}")
        _update(con, "open_calls", call_id, data)


def call_resolve(call_id: int, resolution: str = "", reason: str | None = None) -> None:
    """Close an open call. If it turned into a real choice, also log a decision."""
    with db.write(reason) as con:
        if not con.execute("UPDATE open_calls SET resolved_at = ?, resolution = ? WHERE id = ? AND resolved_at IS NULL",
                           (db.now(), resolution.strip(), call_id)).rowcount:
            raise Error(f"no open call {call_id}")


def call_remove(call_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM open_calls WHERE id = ?", (call_id,)).rowcount:
            raise Error(f"no open call {call_id}")


# --------------------------------------------------------------------------- this week: goals and priorities

def iso_week(d: date | None = None) -> str:
    y, w, _ = (d or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def week_start(week: str) -> date:
    y, w = week.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def _weeks_between(a: str, b: str) -> int:
    return (week_start(b) - week_start(a)).days // 7


def _split_bet(text: str, bet):
    m = re.search(r"\s*#bet(\d+)\b", text)
    if m:
        bet = bet or int(m.group(1))
        text = text[: m.start()] + text[m.end():]
    return " ".join(text.split()), (int(bet) if bet else None)


def _check_bet(con, bet):
    if bet and not con.execute("SELECT 1 FROM bets WHERE n = ?", (bet,)).fetchone():
        raise Error(f"no bet {bet}. Existing bets: " + (", ".join(str(r['n']) for r in con.execute('SELECT n FROM bets ORDER BY n')) or "none"))


def _item(row: dict, week: str, today: str) -> dict:
    row["done"] = row["done_at"] is not None
    row["carried"] = _weeks_between(row["week"], week) if row["kind"] == "goal" else 0
    row["from_day"] = row["day"] if row["kind"] == "priority" and row["day"] and row["day"] < today else None
    return row


def task_snapshot(d: date | None = None, history_weeks: int = 6) -> dict:
    d = d or date.today()
    today, week = d.isoformat(), iso_week(d)
    start = week_start(week)
    with db.read() as con:
        q = lambda sql, *a: [_item(r, week, today) for r in _all(con, sql, *a)]
        goals = q("SELECT * FROM items WHERE kind='goal' AND (week=? OR (week<? AND (done_at IS NULL OR done_at>=?)))"
                  " ORDER BY done_at IS NOT NULL, week, id", week, week, start.isoformat())
        today_items = q("SELECT * FROM items WHERE kind='priority' AND done_at IS NULL AND day<=? ORDER BY day, id", today)
        done = q("SELECT * FROM items WHERE kind='priority' AND done_at>=? ORDER BY done_at", start.isoformat())
        rows = _all(con, "SELECT week, kind, COUNT(*) AS n, SUM(done_at IS NOT NULL) AS d FROM items WHERE week<? GROUP BY week, kind ORDER BY week DESC", week)
    history: dict[str, dict] = {}
    for r in rows:
        h = history.setdefault(r["week"], {"week": r["week"], "goals": 0, "goals_done": 0, "priorities": 0, "priorities_done": 0})
        key = "goals" if r["kind"] == "goal" else "priorities"
        h[key], h[key + "_done"] = r["n"], r["d"]
    return {"week": week, "start": start.isoformat(), "end": (start + timedelta(days=6)).isoformat(), "today": today,
            "goals": goals, "today_items": today_items, "done": done, "history": list(history.values())[:history_weeks]}


def task_add(kind: str, text: str, bet=None, reason: str | None = None) -> int:
    kind = {"goal": "goal", "goals": "goal", "today": "priority", "priority": "priority"}.get(kind)
    if not kind:
        raise Error("kind must be goal or today")
    text, bet = _split_bet(text, bet)
    if not text:
        raise Error("empty text")
    with db.write(reason) as con:
        _check_bet(con, bet)
        return _insert(con, "items", {"kind": kind, "text": text, "bet": bet, "week": iso_week(),
                                      "day": db.today() if kind == "priority" else None, "created_at": db.now()})


def task_done(item_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("UPDATE items SET done_at = ? WHERE id = ? AND done_at IS NULL", (db.now(), item_id)).rowcount \
                and not con.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
            raise Error(f"no item {item_id}")


def task_undo(item_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("UPDATE items SET done_at = NULL, day = CASE WHEN kind='priority' THEN ? ELSE day END WHERE id = ?",
                           (db.today(), item_id)).rowcount:
            raise Error(f"no item {item_id}")


def task_toggle(item_id: int, reason: str | None = None) -> None:
    with db.read() as con:
        row = con.execute("SELECT done_at FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise Error(f"no item {item_id}")
    (task_undo if row["done_at"] else task_done)(item_id, reason)


def task_update(item_id: int, text: str, bet=None, reason: str | None = None) -> None:
    text, bet = _split_bet(text, bet)
    if not text:
        raise Error("empty text")
    with db.write(reason) as con:
        _check_bet(con, bet)
        if not con.execute("UPDATE items SET text = ?, bet = ? WHERE id = ?", (text, bet, item_id)).rowcount:
            raise Error(f"no item {item_id}")


def task_remove(item_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM items WHERE id = ?", (item_id,)).rowcount:
            raise Error(f"no item {item_id}")


def task_week_summary(week: str | None = None) -> str:
    """Plain text for the weekly log entry: goals done, priorities finished, what was carried."""
    week = week or iso_week()
    start = week_start(week)
    end = start + timedelta(days=7)
    with db.read() as con:
        goals = _all(con, "SELECT * FROM items WHERE kind='goal' AND week<=? AND (done_at IS NULL OR done_at>=?) AND created_at<? ORDER BY id",
                     week, start.isoformat(), end.isoformat())
        done = _all(con, "SELECT * FROM items WHERE kind='priority' AND done_at>=? AND done_at<? ORDER BY done_at", start.isoformat(), end.isoformat())
    finished = [g for g in goals if g["done_at"] and g["done_at"] < end.isoformat()]
    out = [f"Week {week}: {len(finished)}/{len(goals)} goals done, {len(done)} priorities finished.", "", "Goals:"]
    for g in goals:
        ok = g["done_at"] and g["done_at"] < end.isoformat()
        carried = _weeks_between(g["week"], week)
        out.append(f"  [{'x' if ok else ' '}] {g['text']}" + (f" (Bet {g['bet']})" if g["bet"] else " (no bet)") + (f" - carried {carried}w" if carried else ""))
    out += ["", "Finished priorities:"]
    out += [f"  {d['done_at'][:10]} {d['text']}" + (f" (Bet {d['bet']})" if d["bet"] else " (no bet)") for d in done] or ["  none"]
    untagged = sum(1 for x in goals + done if not x["bet"])
    if untagged:
        out += ["", f"{untagged} item(s) served no bet."]
    return "\n".join(out)


# --------------------------------------------------------------------------- decisions

def decision_list(due_only: bool = False) -> list[dict]:
    today = db.today()
    with db.read() as con:
        rows = _all(con, "SELECT x.*, d.slug AS department FROM decisions x LEFT JOIN departments d ON d.id = x.department_id ORDER BY x.created_at, x.id")
    for r in rows:
        r["date"] = r["created_at"][:10]
        r["today"] = r["date"] == today
        r["pending"] = not r["outcome"]
        r["due"] = r["pending"] and r["review_on"] <= today
    return [r for r in rows if r["due"]] if due_only else rows


def decision_add(title: str, decided: str, expect: str, review_on: str, why: str = "", department=None,
                 supersedes: int | None = None, created_at: str | None = None, reason: str | None = None) -> int:
    """Expect and Review on are not optional: a decision with no prediction teaches nothing."""
    if not title.strip() or not decided.strip():
        raise Error("a decision needs a title and what was decided")
    if not expect.strip():
        raise Error("--expect is required: what should be true by the review date if this was right?")
    review_on = check_date(review_on, "review date")
    made = (created_at or db.now())[:10]
    if review_on <= made:
        raise Error(f"the review date must be after {made}: when will you check?")
    with db.write(reason) as con:
        return _insert(con, "decisions", {"title": title.strip(), "decided": decided.strip(), "why": why.strip(), "expect": expect.strip(),
                                          "review_on": review_on, "department_id": dept_id(con, department), "supersedes": supersedes,
                                          "created_at": created_at or db.now()})


def decision_outcome(decision_id: int, text: str, reason: str | None = None) -> None:
    if not text.strip():
        raise Error("an outcome says what actually happened: right, wrong or mixed, and what it taught")
    with db.write(reason) as con:
        if not con.execute("UPDATE decisions SET outcome = ?, outcome_at = ? WHERE id = ?", (text.strip(), db.now(), decision_id)).rowcount:
            raise Error(f"no decision {decision_id}")


def decision_update(decision_id: int, reason: str | None = None, **fields) -> None:
    """Allowed on the day it was logged; after that only decision_outcome works (the database enforces it)."""
    data = _pick(fields, ["title", "decided", "why", "expect", "review_on"])
    if "review_on" in data:
        check_date(data["review_on"], "review date")
    with db.write(reason) as con:
        if not con.execute("SELECT 1 FROM decisions WHERE id = ?", (decision_id,)).fetchone():
            raise Error(f"no decision {decision_id}")
        _update(con, "decisions", decision_id, data)


def decision_remove(decision_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM decisions WHERE id = ?", (decision_id,)).rowcount:
            raise Error(f"no decision {decision_id}")


# --------------------------------------------------------------------------- log

def log_list(limit: int = 12, type: str | None = None, since: str | None = None) -> list[dict]:
    where, params = [], []
    if type:
        where.append("l.type = ?"); params.append(type)
    if since:
        where.append("l.date >= ?"); params.append(since)
    with db.read() as con:
        return _all(con, "SELECT l.*, d.slug AS department FROM log_entries l LEFT JOIN departments d ON d.id = l.department_id"
                         f"{' WHERE ' + ' AND '.join(where) if where else ''} ORDER BY l.date DESC, l.id DESC LIMIT ?", *params, limit)


def log_add(type: str, title: str, body: str = "", department=None, date_: str | None = None, reason: str | None = None) -> int:
    if not LOG_TYPE.match(type or ""):
        raise Error("type is one lowercase word, e.g. capture, ingest, weekly, report, decision, change, lint, init")
    if not title.strip():
        raise Error("a log entry needs a title")
    with db.write(reason) as con:
        return _insert(con, "log_entries", {"date": check_date(date_ or db.today()), "type": type, "title": title.strip(), "body": body.strip(),
                                            "department_id": dept_id(con, department), "created_at": db.now()})


def last_log(type: str) -> str | None:
    with db.read() as con:
        row = con.execute("SELECT MAX(date) AS d FROM log_entries WHERE type = ?", (type,)).fetchone()
    return row["d"]


# --------------------------------------------------------------------------- inbox

def inbox_list(open_only: bool = True) -> list[dict]:
    with db.read() as con:
        return _all(con, f"SELECT * FROM inbox{' WHERE filed_at IS NULL' if open_only else ''} ORDER BY id")


def inbox_add(text: str, reason: str | None = None) -> int:
    text = " ".join(text.split())
    if not text:
        raise Error("empty")
    with db.write(reason) as con:
        return _insert(con, "inbox", {"text": text, "created_at": db.now()})


def inbox_file(item_id: int, to: str = "", reason: str | None = None) -> None:
    """Mark an item filed (kept, with where it went). The inbox is 'empty' when nothing is open."""
    with db.write(reason) as con:
        if not con.execute("UPDATE inbox SET filed_at = ?, filed_to = ? WHERE id = ? AND filed_at IS NULL", (db.now(), to, item_id)).rowcount:
            raise Error(f"no open inbox item {item_id}")


def inbox_remove(item_id: int, reason: str | None = None) -> None:
    with db.write(reason) as con:
        if not con.execute("DELETE FROM inbox WHERE id = ?", (item_id,)).rowcount:
            raise Error(f"no inbox item {item_id}")


# --------------------------------------------------------------------------- change history

def changes(limit: int = 50, entity: str | None = None, entity_id: int | None = None, actor: str | None = None) -> list[dict]:
    where, params = [], []
    for col, val in (("entity", entity), ("entity_id", entity_id), ("actor", actor)):
        if val is not None:
            where.append(f"{col} = ?"); params.append(val)
    with db.read() as con:
        rows = _all(con, f"SELECT * FROM changes{' WHERE ' + ' AND '.join(where) if where else ''} ORDER BY id DESC LIMIT ?", *params, limit)
    for r in rows:
        r["before"] = json.loads(r["before"]) if r["before"] else None
        r["after"] = json.loads(r["after"]) if r["after"] else None
        r["summary"] = _summary(r)
    return rows


def _summary(c: dict) -> str:
    row = c["after"] or c["before"] or {}
    label = row.get("title") or row.get("name") or row.get("text") or row.get("question") or row.get("key") or row.get("slug") or f"#{c['entity_id']}"
    if c["action"] == "update" and c["before"] and c["after"]:
        diff = [k for k in c["after"] if c["after"][k] != c["before"].get(k) and k not in ("updated_at",)]
        return f"{label} ({', '.join(diff)})"
    return str(label)[:120]


def history(entity: str, entity_id: int) -> list[dict]:
    return changes(limit=200, entity=entity, entity_id=entity_id)


def revert(change_id: int, reason: str | None = None) -> str:
    """Undo one recorded change by writing the old state back (which is itself recorded)."""
    with db.write(reason or f"revert change {change_id}") as con:
        ch = _one(con, "SELECT * FROM changes WHERE id = ?", change_id)
        if not ch:
            raise Error(f"no change {change_id}")
        table = ch["entity"]
        if table not in db.AUDITED:
            raise Error(f"{table} can't be reverted")
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        before = json.loads(ch["before"]) if ch["before"] else None
        if ch["action"] == "insert":
            con.execute(f"DELETE FROM {table} WHERE id = ?", (ch["entity_id"],))
            return f"removed {table} #{ch['entity_id']} (it was created by change {change_id})"
        data = {k: v for k, v in before.items() if k in cols}
        if ch["action"] == "update":
            _update(con, table, ch["entity_id"], {k: v for k, v in data.items() if k != "id"})
            return f"restored {table} #{ch['entity_id']} to how it was before change {change_id}"
        _insert(con, table, data)
        return f"brought back {table} #{ch['entity_id']} (deleted by change {change_id})"


# --------------------------------------------------------------------------- search

def search(q: str, limit: int = 25) -> list[dict]:
    like = f"%{q}%"
    out: list[dict] = []
    with db.read() as con:
        out += [{"kind": "document", "id": r["slug"], "title": r["title"], "snippet": _snip(r["body"], q)}
                for r in con.execute("SELECT slug, title, body FROM documents WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? LIMIT ?", (like, like, like, limit))]
        out += [{"kind": "decision", "id": r["id"], "title": r["title"], "snippet": _snip(f"{r['decided']} {r['expect']} {r['outcome']}", q)}
                for r in con.execute("SELECT * FROM decisions WHERE title LIKE ? OR decided LIKE ? OR why LIKE ? OR expect LIKE ? OR outcome LIKE ? LIMIT ?", (like,) * 5 + (limit,))]
        out += [{"kind": "log", "id": r["id"], "title": f"[{r['date']}] {r['type']} | {r['title']}", "snippet": _snip(r["body"], q)}
                for r in con.execute("SELECT * FROM log_entries WHERE title LIKE ? OR body LIKE ? ORDER BY date DESC LIMIT ?", (like, like, limit))]
        out += [{"kind": "metric", "id": r["key"], "title": r["name"], "snippet": _snip(r["definition"], q)}
                for r in con.execute("SELECT * FROM metrics WHERE name LIKE ? OR definition LIKE ? OR key LIKE ? LIMIT ?", (like, like, like, limit))]
        out += [{"kind": "inbox", "id": r["id"], "title": r["text"][:80], "snippet": ""}
                for r in con.execute("SELECT * FROM inbox WHERE text LIKE ? LIMIT ?", (like, limit))]
    return out[:limit * 2]


def _snip(text: str, q: str, width: int = 90) -> str:
    text = " ".join((text or "").split())
    i = text.lower().find(q.lower())
    if i < 0:
        return text[:width]
    return ("…" if i > 20 else "") + text[max(0, i - 20): i + width]
