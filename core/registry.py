"""Find the automations: every automations/<name>/automation.json.

An automation is a folder. Delete it and it's gone from the console, the
refresh and the job list. Folders starting with `_` or `.` are skipped.

automation.json (only `label` is required):

  label, description   what it is, in a line
  order                sort position (default 50)
  department           department slug its metrics belong to (used at install)
  env                  variables it needs from automations/.env, e.g. ["YOUTUBE_API_KEY"]
  metrics              metrics it feeds, created on install if missing:
                       [{"key": "mrr", "name": "MRR", "unit": "EUR", "definition": "..."}]
  pull                 steps of "Refresh everything": [{"label", "run": "pull.py", "needs": "glob"}]
                       A pull prints JSON on stdout: {"points": [{"metric": "mrr", "value": 1200, "date": "2026-10-05"}]}
  jobs                 [{"key", "label", "note", "kind": "script" | "claude" | "terminal",
                         "run": "script.py args" | "prompt": "..." | "prompt_file": "prompts/x.md", "tools": [...]}]

Stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import db

ROOT = db.ROOT
AUTO = ROOT / "automations"
CATALOG = ROOT / "catalog"
ENV_FILE = AUTO / ".env"


def automations() -> list[dict]:
    items = []
    for manifest in sorted(AUTO.glob("*/automation.json")):
        folder = manifest.parent
        if folder.name.startswith(("_", ".")):
            continue
        try:
            data = json.loads(manifest.read_text())
        except ValueError as exc:
            print(f"registry: skipping {folder.name}: bad automation.json ({exc})", file=sys.stderr)
            continue
        data.update(name=folder.name, dir=folder, folder=f"automations/{folder.name}")
        data.setdefault("label", folder.name)
        for k in ("pull", "jobs", "env", "metrics"):
            data.setdefault(k, [])
        items.append(data)
    items.sort(key=lambda a: (a.get("order", 50), a["name"]))
    return items


def get(name: str) -> dict | None:
    return next((a for a in automations() if a["name"] == name), None)


def jobs() -> dict[str, tuple[dict, dict]]:
    out: dict[str, tuple[dict, dict]] = {}
    for a in automations():
        for j in a["jobs"]:
            if j["key"] in out:
                print(f"registry: job key {j['key']!r} in {a['name']} is already used by {out[j['key']][0]['name']}", file=sys.stderr)
                continue
            out[j["key"]] = (a, j)
    return out


def env_values() -> dict[str, str]:
    values = {}
    try:
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip("\"'")
    except OSError:
        pass
    return {**values, **{k: v for k, v in os.environ.items() if v}}


def missing_env(a: dict) -> list[str]:
    have = env_values()
    return [k for k in a["env"] if not have.get(k)]


def prompt(a: dict, job: dict) -> str:
    if job.get("prompt_file"):
        return (a["dir"] / job["prompt_file"]).read_text().strip()
    return job.get("prompt", "")


def catalog() -> list[dict]:
    """Use-case packs available to install from catalog/automations/."""
    out = []
    for manifest in sorted((CATALOG / "automations").glob("*/automation.json")):
        data = json.loads(manifest.read_text())
        out.append({"name": manifest.parent.name, "label": data.get("label", manifest.parent.name),
                    "description": data.get("description", ""), "env": data.get("env", []),
                    "installed": (AUTO / manifest.parent.name / "automation.json").exists()})
    return out


def profiles() -> list[dict]:
    """Business starter profiles from catalog/profiles/ (departments + metrics to start from)."""
    out = []
    for path in sorted((CATALOG / "profiles").glob("*.json")):
        data = json.loads(path.read_text())
        out.append({"name": path.stem, "label": data.get("label", path.stem), "description": data.get("description", "")})
    return out
