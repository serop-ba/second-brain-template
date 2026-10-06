#!/usr/bin/env python3
"""Import a markdown second brain (the console version with notes/area-*.md pages) into Brain OS.

  python3 tools/migrate_markdown.py /path/to/second-brain --dry-run     # show what it found
  python3 tools/migrate_markdown.py /path/to/second-brain               # back up, then import
  python3 tools/migrate_markdown.py SRC --db /tmp/test.db               # import into another database

What comes across: company page (a document per section, plus the name as a fact), departments (lead, hours, owns, brief,
page sections), north star, year goals, bets, open calls, decisions (with prediction, review date and outcome), the log (with
bodies), notes, sources (with their ingested flag), video ideas, metrics (definitions, bands) with their full history, the weekly
goals and priorities, the inbox, and your "How I work" rules as the `working-rules` document.

What stays behind: the automations folders (they hold your personal integrations), settings, hooks and the old brain.db.
Nothing in the source folder is changed. The whole import is one transaction: it either all lands or nothing does. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import backup  # noqa: E402
import db  # noqa: E402
import metrics  # noqa: E402
import seed  # noqa: E402
import store  # noqa: E402
from store import _insert, slugify  # noqa: E402

FENCE = re.compile(r"^```.*?^```", re.M | re.S)


# --------------------------------------------------------------------------- reading the old brain

def load_old(src: Path):
    """The old console's own parsers: the same code that rendered it, so the import matches what it showed."""
    path = src / "automations" / "core" / "brain.py"
    if not path.exists():
        sys.exit(f"error: {path} not found. This tool reads the console version of the markdown brain "
                 "(notes/area-*.md pages and automations/core/).")
    core = str(path.parent)
    sys.path.insert(0, core)
    try:
        spec = importlib.util.spec_from_file_location("old_brain", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(core)
        sys.modules.pop("editing", None)
    return mod


def frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def body_of(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def stamp(fm: dict, path: Path) -> str:
    for key in ("updated", "date"):
        if re.match(r"^\d{4}-\d{2}-\d{2}", fm.get(key, "")):
            return fm[key][:10] + "T09:00:00"
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def tags_of(fm: dict) -> str:
    return ",".join(t.strip().strip("\"'").lower() for t in fm.get("tags", "").strip("[]").split(",") if t.strip())


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def clean(cell: str) -> str:
    return cell.replace("**", "").strip("_ ").strip()


def metric_rows(company: str, manual: set) -> list[dict]:
    """The 'Metrics that matter' table: name, department, definition, bands, and a `source:key` that becomes the key."""
    rows, cols = [], None
    for line in company.splitlines():
        if not line.strip().startswith("|"):
            cols = None
            continue
        cells = split_row(line)
        low = [c.lower() for c in cells]
        if "metric" in low and "healthy" in low:
            cols = {n: i for i, n in enumerate(low)}
            continue
        if cols is None or set("".join(cells)) <= set("-: "):
            continue
        cell = lambda n: cells[cols[n]] if n in cols and cols[n] < len(cells) else ""  # noqa: E731
        src = re.search(r"`([a-z_]+:[a-zA-Z0-9_.:]+)`", " ".join(cells))
        if not src or not clean(cell("metric")):
            continue
        alias = src.group(1).partition(":")[0]
        rows.append({"old": src.group(1), "key": key_of(src.group(1)), "name": clean(cell("metric")), "department": clean(cell("department")),
                     "definition": cell("definition").replace("**", "").strip(), "healthy": clean(cell("healthy")),
                     "watch": clean(cell("watch")), "bad": clean(cell("bad")), "source": "manual" if alias in manual else alias})
    return rows


def key_of(old_metric: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", old_metric.lower()).strip("_")


def parse_decisions(text: str) -> list[dict]:
    text = FENCE.sub("", body_of(text))
    out = []
    for m in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})\]\s*(.+?)$(.*?)(?=^## \[|\Z)", text, re.M | re.S):
        f = {k.lower(): " ".join(v.split()) for k, v in re.findall(r"\*\*([A-Z][\w ]*?):\*\*\s*(.*?)(?=\n\*\*[A-Z][\w ]*?:\*\*|\Z)", m.group(3), re.S)}
        outcome = f.get("outcome", "")
        review = (re.search(r"\d{4}-\d{2}-\d{2}", f.get("review on", "")) or [None])[0]
        made = m.group(1)
        out.append({"date": made, "title": m.group(2).strip(), "decided": f.get("decided") or m.group(2).strip(), "why": f.get("why", ""),
                    "expect": f.get("expect") or "(not recorded in the markdown brain)",
                    "review_on": review or (date.fromisoformat(made) + timedelta(days=30)).isoformat(),
                    "outcome": "" if not outcome or outcome.startswith("_(") else outcome})
    return out


def parse_log(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})\]\s*([\w-]+)\s*\|\s*(.+?)$(.*?)(?=^## \[|\Z)", body_of(text), re.M | re.S):
        kind = m.group(2).lower()
        out.append({"date": m.group(1), "type": kind if store.LOG_TYPE.match(kind) else "note", "title": m.group(3).strip(), "body": m.group(4).strip()})
    return out


def read_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(errors="ignore")
    return frontmatter(text), body_of(text)


def collect(src: Path, skip_output: bool, manual: set) -> dict:
    old = load_old(src)
    company = (src / "company.md").read_text() if (src / "company.md").exists() else ""
    data: dict = {"goals": old.parse_goals(), "areas": old.parse_areas(), "inbox": old.parse_inbox(), "company_departments": old.departments()}
    data["metrics"] = metric_rows(company, manual)
    data["decisions"] = parse_decisions((src / "decisions.md").read_text()) if (src / "decisions.md").exists() else []
    data["log"] = parse_log((src / "log.md").read_text()) if (src / "log.md").exists() else []
    data["company_sections"] = [(t, b.strip()) for t, b in old.split_sections(body_of(company), 2) if b.strip()] if company else []
    m = re.search(r"## What it is\s+\*\*(.+?)\*\*", company)
    data["company_name"] = m.group(1) if m else ""
    data["company_updated"] = frontmatter(company).get("updated", "")
    docs = []
    for path in sorted((src / "notes").glob("*.md")) if (src / "notes").exists() else []:
        fm, body = read_md(path)
        if fm.get("type") == "area":
            continue
        docs.append({"kind": "note", "title": fm.get("title") or path.stem.replace("-", " ").title(), "body": body, "tags": tags_of(fm), "ts": stamp(fm, path), "ref": ""})
    for path in sorted((src / "raw").glob("*.md")) if (src / "raw").exists() else []:
        fm, body = read_md(path)
        docs.append({"kind": "source", "title": fm.get("title") or path.stem, "body": body, "tags": tags_of(fm), "ts": stamp(fm, path),
                     "ref": fm.get("source", ""), "ingested": int(fm.get("ingested", "").lower() == "true")})
    if not skip_output:
        for path in sorted((src / "Output" / "video-ideas").glob("*.md")) if (src / "Output" / "video-ideas").exists() else []:
            fm, body = read_md(path)
            docs.append({"kind": "note", "title": fm.get("title") or path.stem, "body": body, "tags": "video-idea", "ts": stamp(fm, path),
                         "ref": fm.get("source", ""), "dept": "marketing"})
    data["documents"] = docs
    rules = ""
    if (src / "CLAUDE.md").exists():
        mm = re.search(r"^## How I work\s*\n(.*?)(?=^## |\Z)", (src / "CLAUDE.md").read_text(), re.M | re.S)
        rules = mm.group(1).strip() if mm else ""
    data["rules"] = rules
    data["old_db"] = src / "automations" / "core" / "data" / "brain.db"
    return data


def read_old_db(path: Path) -> tuple[list, list, dict]:
    """items, metric history and metric names from the old console database (copied first: it may be in WAL mode)."""
    if not path.exists():
        return [], [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in ("", "-wal", "-shm"):
            if Path(str(path) + suffix).exists():
                shutil.copyfile(str(path) + suffix, Path(tmp) / ("old.db" + suffix))
        con = sqlite3.connect(Path(tmp) / "old.db")
        con.row_factory = sqlite3.Row
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        items = [dict(r) for r in con.execute("SELECT * FROM items")] if "items" in have else []
        hist = [dict(r) for r in con.execute("SELECT * FROM metric_history")] if "metric_history" in have else []
        names = {r["metric"]: r["name"] for r in con.execute("SELECT metric, name FROM metrics")} if "metrics" in have else {}
        con.close()
    return items, hist, names


# --------------------------------------------------------------------------- writing

def band(value: str) -> str:
    try:
        return metrics.check_band(value, "band")
    except store.Error:
        return ""


def apply(data: dict, src: Path) -> dict:
    items, hist, names = read_old_db(data["old_db"])
    n = {k: 0 for k in ("departments", "sections", "documents", "bets", "goals", "calls", "decisions", "log", "inbox", "metrics", "points", "items")}
    now = db.now()
    with db.write("migrated from the markdown second brain", who="migration") as con:
        # departments
        dept_ids: dict[str, int] = {}
        for i, a in enumerate(data["areas"]):
            did = _insert(con, "departments", {"slug": a["slug"], "name": a["department"], "owner": a["owner"], "hours": a["hours"], "owns": a["owns"],
                                               "intro": a["intro"], "position": i + 1, "created_at": now, "updated_at": now})
            dept_ids[a["slug"]] = did
            n["departments"] += 1
            brief = a["brief"]
            if brief:
                briefed = re.search(r"_Briefed (\d{4}-\d{2}-\d{2})", brief)
                con.execute("UPDATE departments SET brief = ?, briefed_at = ? WHERE id = ?", (re.sub(r"^_Briefed[^\n]*_\s*", "", brief).strip(), briefed.group(1) if briefed else None, did))
            for j, s in enumerate(x for x in a["sections"] if not re.match(r"how to feed", x["title"], re.I)):
                _insert(con, "documents", {"slug": f"{a['slug']}/{slugify(s['title'])}", "title": s["title"], "kind": "section", "department_id": did,
                                           "body": s["body"], "position": j, "created_at": now, "updated_at": now})
                n["sections"] += 1
        by_name = {a["department"].lower(): a["slug"] for a in data["areas"]}

        def dept_of(text: str) -> int | None:
            text = (text or "").lower()
            slug = by_name.get(text) or next((s for name, s in by_name.items() if name and name in text), None)
            return dept_ids.get(slug) if slug else None

        # direction
        g = data["goals"]
        if g["north_star"]:
            _insert(con, "goals", {"level": "north_star", "text": g["north_star"], "detail": g["north_star_detail"], "created_at": now, "updated_at": now})
            n["goals"] += 1
        for i, y in enumerate((g["year"] or {}).get("goals", [])):
            _insert(con, "goals", {"level": "year", "text": y["text"], "detail": y["detail"], "position": i + 1, "created_at": now, "updated_at": now})
            n["goals"] += 1
        year = re.search(r"\d{4}", (g["year"] or {}).get("title", ""))
        if year:
            con.execute("INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES ('planning_year', ?, ?)", (year.group(0), now))
        for b in g["bets"]:
            _insert(con, "bets", {"n": b["n"], "title": b["title"], "department_id": dept_of(b["department"]), "why": b["why"], "success": b["success"],
                                  "status": b["status"] or "not started", "status_note": b["status_note"], "next_steps": "\n".join(b["next"]),
                                  "created_at": now, "updated_at": now})
            n["bets"] += 1
        for c in g["open_decisions"]:
            _insert(con, "open_calls", {"question": re.sub(r"[*_]", "", c["question"]).strip(), "context": c["context"], "created_at": now})
            n["calls"] += 1

        # company: facts and one document per section
        if data["company_name"]:
            con.execute("INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES ('name', ?, ?)", (data["company_name"], now))
        for title, body in data["company_sections"]:
            _insert(con, "documents", {"slug": f"company-{slugify(title)}", "title": f"Company: {title}", "kind": "note", "tags": "company", "body": body,
                                       "created_at": now, "updated_at": (data["company_updated"] or now[:10]) + "T09:00:00"})
            n["documents"] += 1
        if data["rules"]:
            _insert(con, "documents", {"slug": "working-rules", "title": "Working rules", "kind": "playbook", "tags": "rules", "body": data["rules"],
                                       "created_at": now, "updated_at": now})
            n["documents"] += 1

        # documents
        taken = {r[0] for r in con.execute("SELECT slug FROM documents")}
        for d in data["documents"]:
            base, slug, k = slugify(d["title"]), None, 1
            slug = base
            while slug in taken:
                k += 1
                slug = f"{base}-{k}"
            taken.add(slug)
            dept_slug = d.get("dept") or next((a["slug"] for a in data["areas"] if a["slug"] in d["tags"].split(",")), None)
            _insert(con, "documents", {"slug": slug, "title": d["title"], "kind": d["kind"], "department_id": dept_ids.get(dept_slug), "tags": d["tags"],
                                       "body": d["body"], "ingested": d.get("ingested", 0), "source_ref": d["ref"], "created_at": d["ts"], "updated_at": d["ts"]})
            n["documents"] += 1

        # events
        for x in data["decisions"]:
            _insert(con, "decisions", {"title": x["title"], "decided": x["decided"], "why": x["why"], "expect": x["expect"], "review_on": x["review_on"],
                                       "outcome": x["outcome"], "outcome_at": (x["date"] + "T09:00:00") if x["outcome"] else None, "created_at": x["date"] + "T09:00:00"})
            n["decisions"] += 1
        for e in data["log"]:
            _insert(con, "log_entries", {"date": e["date"], "type": e["type"], "title": e["title"], "body": e["body"], "created_at": e["date"] + "T09:00:00"})
            n["log"] += 1
        for line in data["inbox"]:
            _insert(con, "inbox", {"text": re.sub(r"^- ", "", line), "created_at": now})
            n["inbox"] += 1

        # numbers
        key_for: dict[str, str] = {}
        metric_ids: dict[str, int] = {}
        for i, m in enumerate(data["metrics"]):
            key_for[m["old"]] = m["key"]
            metric_ids[m["key"]] = _insert(con, "metrics", {"key": m["key"], "name": m["name"], "department_id": dept_of(m["department"]), "definition": m["definition"],
                                                            "source": m["source"], "healthy": band(m["healthy"]), "watch": band(m["watch"]), "bad": band(m["bad"]),
                                                            "position": i + 1, "created_at": now, "updated_at": now})
            n["metrics"] += 1
        manual_origin = {m["old"]: m["source"] == "manual" for m in data["metrics"]}
        for h in hist:
            key = key_of(h["metric"])
            if key not in metric_ids:  # history of a metric no longer in company.md
                metric_ids[key] = _insert(con, "metrics", {"key": key, "name": names.get(h["metric"], h["metric"]), "source": h["metric"].partition(":")[0],
                                                           "position": len(metric_ids) + 1, "created_at": now, "updated_at": now})
                n["metrics"] += 1
            origin = "manual" if (h["origin"] == "ledger" or manual_origin.get(h["metric"])) else h["metric"].partition(":")[0]
            _insert(con, "metric_points", {"metric_id": metric_ids[key], "as_of": h["as_of"], "value": h["value"], "origin": origin, "recorded_at": h["recorded_at"],
                                           "deleted_at": h.get("deleted_at")})
            n["points"] += 1
        for it in items:
            _insert(con, "items", {k: it[k] for k in ("kind", "text", "bet", "week", "day", "done_at", "created_at")})
            n["items"] += 1
        _insert(con, "log_entries", {"date": db.today(), "type": "change", "title": "Migrated from the markdown second brain",
                                     "body": ", ".join(f"{v} {k}" for k, v in n.items() if v) + f". Source: {src.name}. Nothing was deleted from the source folder.",
                                     "created_at": now})
    db.meta_set("initialized", "1")
    return n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("source", help="path to the markdown second brain")
    p.add_argument("--dry-run", action="store_true", help="read and count, write nothing")
    p.add_argument("--db", help="import into this database file instead of data/brain.db")
    p.add_argument("--skip-output", action="store_true", help="don't import Output/video-ideas")
    p.add_argument("--manual-sources", default="finance", help="comma list of metric source aliases that are hand-logged ledgers (default: finance)")
    p.add_argument("--force", action="store_true", help="import even though this brain already has data")
    args = p.parse_args()
    if args.db:
        os.environ["BRAIN_DB"] = args.db
    src = Path(args.source).expanduser().resolve()
    if not (src / "CLAUDE.md").exists():
        sys.exit(f"error: {src} doesn't look like a second brain (no CLAUDE.md)")
    data = collect(src, args.skip_output, {s.strip() for s in args.manual_sources.split(",") if s.strip()})
    items, hist, _ = read_old_db(data["old_db"])
    found = {"departments": len(data["areas"]), "department sections": sum(len(a["sections"]) for a in data["areas"]), "bets": len(data["goals"]["bets"]),
             "year goals": len((data["goals"]["year"] or {}).get("goals", [])), "open calls": len(data["goals"]["open_decisions"]), "decisions": len(data["decisions"]),
             "log entries": len(data["log"]), "documents (notes, sources, ideas, company sections)": len(data["documents"]) + len(data["company_sections"]),
             "metrics": len(data["metrics"]), "metric points": len(hist), "weekly goals and priorities": len(items), "inbox items": len(data["inbox"]),
             "working rules": 1 if data["rules"] else 0}
    print(f"Found in {src}:")
    for k, v in found.items():
        print(f"  {v:>5}  {k}")
    if args.dry_run:
        print("\nDry run: nothing written.")
        return
    with db.read():
        pass
    if seed.is_demo():
        print("\nClearing demo data first (backup made).")
        backup.backup("before-migration")
        seed.clear()
    elif seed.has_user_data() and not args.force:
        sys.exit("error: this brain already has data. Use --db for a fresh file, or --force to import alongside it.")
    else:
        backup.backup("before-migration")
    counts = apply(data, src)
    print("\nImported:")
    for k, v in counts.items():
        print(f"  {v:>5}  {k}")
    print(f"\nDone. Database: {db.db_path()}\nNext: python3 brain.py context, then python3 brain.py serve.\n"
          "Then ask Claude: \"Distil my company documents into company facts (stage, hours, runway, kill condition) and check the metric bands.\"")


if __name__ == "__main__":
    main()
