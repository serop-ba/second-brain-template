"""The brain as a graph, for the Overview's orbit map.

Every node is something real in the database or the repo: the schema (the sun),
one planet per department, and around them its documents, metrics, decisions and
log entries, plus the skills and automations on the outer rings. Nothing is
invented to make the picture fuller: an empty brain draws an empty sky. Stdlib only.
"""

from __future__ import annotations

import re

import db
import metrics
import registry
import store

SYSTEM = "system"


def build() -> dict:
    depts = store.dept_list()
    slugs = {d["id"]: d["slug"] for d in depts}
    dept_of = lambda dept_id: slugs.get(dept_id, SYSTEM)  # noqa: E731
    nodes: list[dict] = []
    links: list[list[str]] = []
    add = lambda **n: nodes.append(n)  # noqa: E731

    add(id="core", kind="core", label=store.profile_get().get("name", "Brain"), dept=SYSTEM, path="CLAUDE.md")
    for d in depts:
        add(id=f"area:{d['slug']}", kind="area", label=d["name"], dept=d["slug"], path=f"department: {d['slug']}")
        links.append(["core", f"area:{d['slug']}"])
    add(id=f"area:{SYSTEM}", kind="area", label="System", dept=SYSTEM, path="")

    doc_ids: dict[str, str] = {}
    docs = store.doc_list(with_body=True)
    for d in docs:
        if d["kind"] == "section":
            continue
        nid = f"doc:{d['slug']}"
        doc_ids[d["slug"]] = nid
        add(id=nid, kind="file", label=d["title"], dept=dept_of(d["department_id"]), sub=d["kind"], path=f"library: {d['slug']}", doc=d["slug"])
        if d["department_id"]:
            links.append([f"area:{d['department']}", nid])
    for d in docs:
        for target in set(re.findall(r"\[\[([^\]|#]+)", d.get("body", "") or "")):
            slug = store.slugify(target)
            if slug in doc_ids and d["slug"] in doc_ids and slug != d["slug"]:
                links.append([doc_ids[d["slug"]], doc_ids[slug]])

    for skill in sorted((db.ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        add(id=f"skill:{skill.parent.name}", kind="skill", label=skill.parent.name, dept=SYSTEM, path=f".claude/skills/{skill.parent.name}")

    owner: dict[str, str] = {}
    for a in registry.automations():
        dept = a.get("department") if a.get("department") in slugs.values() else SYSTEM
        aid = f"app:{a['name']}"
        add(id=aid, kind="app", label=a["label"], dept=dept, path=a["folder"])
        owner[a["name"]] = aid
        for j in a["jobs"]:
            add(id=f"job:{j['key']}", kind="routine", label=j["label"], dept=dept, path=a["folder"], parent=aid)
            links.append([aid, f"job:{j['key']}"])

    for e in store.log_list(400):
        add(id=f"log:{e['id']}", kind="run", label=e["title"], dept=e["department"] or SYSTEM, path="log", sub=e["type"], date=e["date"])
    for x in store.decision_list():
        nid = f"decision:{x['id']}"
        add(id=nid, kind="decision", label=x["title"], dept=x["department"] or SYSTEM, path="decisions", date=x["date"], due=x["due"], did=x["id"])
        if x["department"]:
            links.append([f"area:{x['department']}", nid])
    for m in metrics.metric_list(with_points=False):
        nid = f"metric:{m['key']}"
        add(id=nid, kind="metric", label=m["name"], dept=m["department"] or SYSTEM, path="numbers", verdict=m["verdict"],
            sub="" if m["now"] is None else f"{m['now']:g}", key=m["key"])
        if m["department"]:
            links.append([f"area:{m['department']}", nid])
        if m["source"] in owner:
            links.append([owner[m["source"]], nid])

    seen, unique = set(), []
    for a, b in links:
        key = tuple(sorted((a, b)))
        if key not in seen:
            seen.add(key)
            unique.append([a, b])
    return {"nodes": nodes, "links": unique,
            "counts": {"files": sum(n["kind"] in ("file", "skill") for n in nodes) + len(depts) + 1, "links": len(unique),
                       "runs": sum(n["kind"] == "run" for n in nodes)}}
