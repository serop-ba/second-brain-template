"""Install use-case packs and starter profiles from catalog/.

  python3 brain.py automation install youtube   # copies catalog/automations/youtube -> automations/youtube
  python3 brain.py profile apply creator        # adds that profile's departments and metrics

Both only ever add: an existing department, metric or folder is left alone. Stdlib only.
"""

from __future__ import annotations

import json
import shutil

import db
import metrics
import registry
import store
from store import Error


def install_automation(name: str) -> dict:
    src = registry.CATALOG / "automations" / name
    if not (src / "automation.json").exists():
        names = ", ".join(p["name"] for p in registry.catalog()) or "none"
        raise Error(f"no pack {name!r} in catalog/automations. Available: {names}")
    dest = registry.AUTO / name
    if dest.exists():
        raise Error(f"automations/{name} is already installed (delete the folder to reinstall)")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = json.loads((dest / "automation.json").read_text())
    existing = {m["key"] for m in metrics.metric_list(with_points=False)}
    depts = {d["slug"] for d in store.dept_list()}
    created = []
    for m in manifest.get("metrics", []):
        if m["key"] in existing:
            continue
        dept = manifest.get("department") if manifest.get("department") in depts else None
        metrics.metric_add(m["key"], m["name"], reason=f"installed {name}", department=dept, unit=m.get("unit", ""),
                           definition=m.get("definition", ""), source=name)
        created.append(m["key"])
    env = manifest.get("env", [])
    return {"name": name, "metrics_created": created, "env": env,
            "next": (f"Put {', '.join(env)} in automations/.env (copy automations/.env.example), then: python3 brain.py refresh {name}"
                     if env else f"Run: python3 brain.py refresh {name}")}


def remove_automation(name: str) -> None:
    dest = registry.AUTO / name
    if not (dest / "automation.json").exists():
        raise Error(f"automations/{name} isn't installed")
    shutil.rmtree(dest)


def apply_profile(name: str) -> dict:
    path = registry.CATALOG / "profiles" / f"{name}.json"
    if not path.exists():
        names = ", ".join(p["name"] for p in registry.profiles()) or "none"
        raise Error(f"no profile {name!r}. Available: {names}")
    data = json.loads(path.read_text())
    have_d = {d["slug"] for d in store.dept_list()}
    have_m = {m["key"] for m in metrics.metric_list(with_points=False)}
    added_d, added_m = [], []
    for d in data.get("departments", []):
        slug = store.slugify(d.get("slug") or d["name"])
        if slug in have_d:
            continue
        store.dept_add(d["name"], slug=slug, reason=f"profile {name}", owns=d.get("owns", ""), intro=d.get("intro", ""))
        added_d.append(slug)
    for m in data.get("metrics", []):
        if m["key"] in have_m:
            continue
        metrics.metric_add(m["key"], m["name"], reason=f"profile {name}", department=m.get("department"), unit=m.get("unit", ""),
                           definition=m.get("definition", ""), healthy=m.get("healthy", ""), watch=m.get("watch", ""), bad=m.get("bad", ""))
        added_m.append(m["key"])
    return {"profile": name, "departments": added_d, "metrics": added_m}
