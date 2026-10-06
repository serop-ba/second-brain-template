"""Pull everything and record the numbers.

  python3 brain.py refresh            # every pull, in order
  python3 brain.py refresh youtube    # just one automation

A pull is a script that prints JSON on stdout: {"points": [{"metric": key, "value": n, "date": "YYYY-MM-DD"}]}.
A failed pull doesn't stop the run: the others still record, and the metric it
feeds keeps its last real value instead of a guess. Each outcome lands in
`automation_runs` and in meta `last_refresh`. Stdlib only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import db
import metrics
import registry


def parse_output(stdout: str) -> dict:
    text = stdout.strip()
    for candidate in (text, text.splitlines()[-1] if text else ""):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except ValueError:
            continue
    raise ValueError("the pull didn't print JSON like {\"points\": [...]} on stdout")


def run_pull(a: dict, step: dict, say=print) -> dict:
    """Run one pull step. Returns {ok, skipped?, recorded, unmapped, message}."""
    label = f"{a['label']}: {step.get('label', step['run'])}"
    needs = step.get("needs")
    if needs and not any(a["dir"].glob(needs)):
        return {"ok": True, "skipped": True, "message": f"skipped, nothing matches {a['folder']}/{needs} yet"}
    missing = registry.missing_env(a)
    if missing:
        return {"ok": False, "message": f"missing in automations/.env: {', '.join(missing)}"}
    script, *args = step["run"].split()
    proc = subprocess.run([sys.executable, str(a["dir"] / script), *args], cwd=a["dir"], capture_output=True, text=True,
                          env={**os.environ, **registry.env_values()}, timeout=300)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return {"ok": False, "message": " | ".join(tail) or f"exit {proc.returncode}"}
    try:
        data = parse_output(proc.stdout)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}
    result = metrics.record_points(a["name"], data.get("points", []), reason=f"pull: {label}")
    msg = f"recorded {result['recorded']} value(s)"
    if result["unmapped"]:
        msg += f"; no metric for: {', '.join(result['unmapped'])} (add with: metric add <key> ...)"
    return {"ok": True, "message": msg, **result}


def refresh(only: str | None = None, say=print) -> dict:
    started = time.time()
    steps = [(a, s) for a in registry.automations() if not only or a["name"] == only for s in a["pull"]]
    failed = []
    if only and not steps:
        say(f"no pulls to run for {only!r}")
    for a, step in steps:
        label = f"{a['label']}: {step.get('label', step['run'])}"
        say(f"▸ {label}")
        began = db.now()
        res = run_pull(a, step, say)
        say(f"  {'ok' if res['ok'] else 'failed'}: {res['message']}")
        if not res["ok"]:
            failed.append(label)
        with db.write("refresh", who=f"automation:{a['name']}") as con:
            con.execute("INSERT INTO automation_runs (automation, job_key, label, kind, status, started_at, ended_at, output) VALUES (?,?,?,?,?,?,?,?)",
                        (a["name"], "pull", label, "pull", "skipped" if res.get("skipped") else ("ok" if res["ok"] else "failed"), began, db.now(), res["message"]))
    status = {"at": db.now(), "ok": not failed, "failed": failed, "seconds": round(time.time() - started, 1), "pulls": len(steps)}
    db.meta_set("last_refresh", json.dumps(status))
    say(f"\n{'Done' if not failed else 'Done, with failures: ' + ', '.join(failed)} in {status['seconds']}s.")
    return status


def last_status() -> dict | None:
    raw = db.meta_get("last_refresh")
    return json.loads(raw) if raw else None


def due(at: str | None) -> bool:
    """True when a daily refresh is set for `at` (HH:MM) and its latest run time passed without one."""
    from datetime import datetime, timedelta
    if not at:
        return False
    hour, minute = (int(x) for x in at.split(":"))
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target > now:
        target -= timedelta(days=1)
    last = (last_status() or {}).get("at")
    return not last or datetime.fromisoformat(last) < target
