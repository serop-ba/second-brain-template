"""Run jobs for the console: scripts, headless Claude, and Claude in a terminal.

Headless Claude is deliberately boxed in: it may read files and run
`brain.py` and nothing else, so everything it changes goes through the audited
CLI (Edit/Write are only granted to a job that asks for them with `tools`).
It never commits or pushes. Stdlib only.
"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import db
import registry
import store

ROOT = db.ROOT
BRAIN = str(ROOT / "brain.py")
PYCMD = "python" if sys.platform == "win32" else "python3"
CLI = f"{PYCMD} brain.py"

CORE_SCRIPTS = {
    "refresh": ("Refresh everything", "Runs every automation's pull and records today's numbers.", [sys.executable, BRAIN, "refresh"]),
    "backup": ("Back up now", "A consistent copy of the database in data/backups/.", [sys.executable, BRAIN, "backup"]),
}

READ_FIRST = f"Start with `{CLI} context --full` to load the business. Change data only with `{CLI}` (see CLAUDE.md); never edit files."

AREA_BRIEF = (
    "You are the lead of the {dept} department, briefing the founder. " + READ_FIRST + " Then read that department's "
    "page with `" + CLI + " dept show {slug}` and the recent log with `" + CLI + " log list --since 30d`. Write ONLY its brief with "
    "`" + CLI + " dept brief {slug} --text \"...\"`: open with `**Headline:**` and one sentence on where {dept} stands against "
    "the bets, then bold-labelled bullets: **Doing** (what is actually being worked on, with evidence and dates), **Stuck** "
    "(what is blocked and on whom), **Next** (at most three actions, each tied to a bet or open decision), **Ask of the founder** "
    "(the one call only they can make, or `none`). Then update the department's sections that went stale with "
    "`" + CLI + " doc update <slug> --body \"...\"`, noting any claim you revise inline with its date. Never invent a number: "
    "no data is a finding, so say it. If the department gets ~0 hours a week, say what that costs the bets."
)

CORE_CLAUDE = {
    "weekly": ("Weekly loop", "Inbox, numbers, bets, decisions due, then the weekly log entry.",
               "Run the weekly loop exactly as CLAUDE.md defines it, every step. " + READ_FIRST),
    "plan_day": ("Plan my day", "Picks at most three priorities that move a bet.",
                 "Plan today. " + READ_FIRST + f" Leave Today with at most three open priorities, the ones that most move a bet this week "
                 f"(`{CLI} task add today \"text\" --bet N`, `task rm ID`). Reply with one line per priority saying why it won, and one line "
                 "naming what you deliberately left off."),
    "plan_week": ("Plan my week", "Proposes 3-5 outcomes and calls out stale goals.",
                  "Plan this week. " + READ_FIRST + f" Leave 3-5 open weekly goals (outcomes, not activities) that move the bets "
                  f"(`{CLI} task add goal \"text\" --bet N`). A goal carried 2+ weeks: cut it or say why it earns another week. "
                  "Reply with the goals and the one you'd cut first if the week goes badly."),
    "inbox": ("Empty inbox", "Files every inbox item where it belongs.",
              "Run step 1 of the weekly loop in CLAUDE.md only: file every inbox item into the right place " + f"(`{CLI} inbox list`, then `inbox file ID --to ...`). "
              "Reply with where each item went."),
    "lint": ("Lint the brain", "Contradictions, stale claims, overdue reviews.",
             "Lint the brain as CLAUDE.md defines it and log the result with `" + CLI + " log add --type lint`."),
    "areas": ("Brief every department", "Each department lead writes a brief, then the hand-offs between them.",
              "Brief every department. For each department in `" + CLI + " dept list`, do exactly this, as that department's lead:\n\n{brief}\n\n"
              "Then reply with the hand-offs between departments: who is waiting on whom, and the one cross-department move that unblocks the most."),
}

CORE_TERMINAL = {
    "session": ("Open Claude", "A fresh Claude session in this folder.", ""),
    "init": ("Set up my business", "The /init interview: Claude fills the brain from your answers.", "/init"),
    "weekly": ("Weekly loop, with you", "The weekly loop as a conversation.", "/weekly"),
    "record": ("Record something", "Log a decision, change or experiment.", "/record"),
    "ingest": ("Ingest a source", "Turn a source document into notes.", "/ingest"),
    "connect": ("Connect a tool", "Wire a catalog pack or build a new automation.", "/connect"),
}

HEADLESS_TOOLS = ["Read", "Glob", "Grep", "Bash(python3 brain.py *)", "Bash(python brain.py *)"]
HEADLESS_NOTE = ("You are running headless from the console; nobody can answer questions mid-run, so decide and say what you decided. "
                 "One command per Bash call. Never commit or push. End with a short summary.")


class Job:
    def __init__(self, job_id: str, key: str, label: str, kind: str, arg: str | None = None):
        self.id, self.key, self.label, self.kind, self.arg = job_id, key, label, kind, arg
        self.lines: list[str] = []
        self.status = "running"  # running | ok | failed | stopped
        self.started = time.time()
        self.ended: float | None = None
        self.proc: subprocess.Popen | None = None
        self.stopped = False

    def say(self, text: str) -> None:
        self.lines.extend(text.rstrip("\n").split("\n"))
        if len(self.lines) > 4000:
            self.lines = self.lines[:200] + ["... (output truncated) ..."] + self.lines[-3000:]

    def public(self, since: int = 0) -> dict:
        return {"id": self.id, "key": self.key, "label": self.label, "kind": self.kind, "arg": self.arg, "status": self.status,
                "started": self.started, "ended": self.ended, "lines": self.lines[since:], "total": len(self.lines)}


JOBS: dict[str, Job] = {}


def claude_bin() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    for fallback in (Path.home() / ".local" / "bin" / "claude", Path.home() / ".claude" / "local" / "claude"):
        if fallback.exists():
            return str(fallback)
    return None


def run_proc(job: Job, cmd: list[str], on_line=None, cwd: Path = ROOT, env: dict | None = None) -> int:
    job.proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                env={**os.environ, "BRAIN_ACTOR": "automation", **(env or {})})
    for line in job.proc.stdout:
        (on_line or job.say)(line)
    return job.proc.wait()


def _summarize_tool(name: str, data: dict) -> str:
    for field in ("command", "file_path", "pattern", "path", "description", "skill"):
        if data.get(field):
            return f"{name}: {str(data[field]).replace(str(ROOT) + os.sep, '')[:140]}"
    return name


def _claude_line(job: Job):
    def handle(raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            event = json.loads(raw)
        except ValueError:
            job.say(raw)
            return
        kind = event.get("type")
        if kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and block.get("text", "").strip():
                    job.say(block["text"].strip())
                elif block.get("type") == "tool_use":
                    job.say("→ " + _summarize_tool(block.get("name", "tool"), block.get("input") or {}))
        elif kind == "user":
            for block in event.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                    content = block.get("content")
                    text = content if isinstance(content, str) else json.dumps(content)
                    job.say("  ✗ " + text.strip().split("\n")[0][:200])
        elif kind == "result":
            for denial in event.get("permission_denials") or []:
                job.say("  ⛔ blocked: " + _summarize_tool(denial.get("tool_name", "tool"), denial.get("tool_input") or {}))
            cost, turns = event.get("total_cost_usd"), event.get("num_turns")
            tail = ", ".join(x for x in [f"{turns} turns" if turns else "", f"${cost:.2f}" if cost else ""] if x)
            job.say(f"— {'error' if event.get('is_error') else 'done'}{' (' + tail + ')' if tail else ''}")
    return handle


def run_claude(job: Job, prompt: str, tools: list[str] = ()) -> int:
    binary = claude_bin()
    if not binary:
        job.say("error: `claude` not found on PATH. Install Claude Code, or start the console from a shell that has it.")
        return 127
    job.say("$ claude -p ... (headless: can read files and run brain.py; every change is recorded)")
    cmd = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
           "--allowedTools", ",".join([*HEADLESS_TOOLS, *tools]), "--append-system-prompt", HEADLESS_NOTE]
    return run_proc(job, cmd, _claude_line(job), env={"BRAIN_ACTOR": "claude"})


def _resolve(key: str, prompt: str | None) -> tuple[str, str, callable]:
    if key in CORE_SCRIPTS:
        label, _, cmd = CORE_SCRIPTS[key]
        return label, "script", lambda job: run_proc(job, cmd)
    if key in CORE_CLAUDE:
        label, _, text = CORE_CLAUDE[key]
        text = text.replace("{brief}", AREA_BRIEF.format(dept="<the department>", slug="<slug>"))
        return label, "claude", lambda job: run_claude(job, text)
    if key.startswith("brief:"):
        dept = next((d for d in store.dept_list() if d["slug"] == key[6:]), None)
        if not dept:
            raise ValueError(f"no department {key[6:]!r}")
        text = AREA_BRIEF.format(dept=dept["name"], slug=dept["slug"])
        return f"Brief {dept['name']}", "claude", lambda job: run_claude(job, text)
    if key == "ask":
        if not (prompt or "").strip():
            raise ValueError("empty prompt")
        return "Ask: " + prompt.strip()[:60], "claude", lambda job: run_claude(job, READ_FIRST + "\n\n" + prompt)
    found = registry.jobs().get(key)
    if not found or found[1].get("kind") == "terminal":
        raise ValueError(f"unknown job {key!r}")
    a, spec = found
    if spec["kind"] == "script":
        script, *args = spec["run"].split()
        return spec["label"], "script", lambda job: run_proc(job, [sys.executable, str(a["dir"] / script), *args], cwd=a["dir"], env=registry.env_values())
    text = registry.prompt(a, spec)
    return spec["label"], "claude", lambda job: run_claude(job, text, spec.get("tools", []))


def start_job(key: str, prompt: str | None = None, arg: str | None = None) -> Job:
    for existing in JOBS.values():
        if existing.key == key and existing.arg == arg and existing.status == "running":
            return existing
    label, kind, work = _resolve(key, prompt)
    job = Job(secrets.token_hex(4), key, label, kind, arg)
    JOBS[job.id] = job

    def run() -> None:
        began = db.now()
        try:
            code = work(job)
            job.status = "stopped" if job.stopped else ("ok" if code == 0 else "failed")
        except Exception as exc:  # shown in the console, not swallowed
            job.say(f"error: {exc}")
            job.status = "failed"
        job.ended = time.time()
        try:
            with db.write("job", who="console") as con:
                con.execute("INSERT INTO automation_runs (automation, job_key, label, kind, status, started_at, ended_at, output) VALUES (?,?,?,?,?,?,?,?)",
                            ((registry.jobs().get(key) or ({"name": "core"},))[0]["name"], key, label, kind, job.status, began, db.now(), "\n".join(job.lines[-60:])))
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()
    return job


def terminal_prompt(key: str) -> str:
    if key in CORE_TERMINAL:
        return CORE_TERMINAL[key][2]
    found = registry.jobs().get(key)
    if found and found[1].get("kind") == "terminal":
        return registry.prompt(*found)
    raise ValueError("unknown terminal job")


def open_terminal(key: str) -> dict:
    """macOS opens Terminal.app; everywhere else the console shows the command to paste."""
    prompt = terminal_prompt(key)
    cmd = f"cd {shlex.quote(str(ROOT))} && claude" + (f" {shlex.quote(prompt)}" if prompt else "")
    if sys.platform == "darwin":
        escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(["osascript", "-e", f'tell application "Terminal" to do script "{escaped}"', "-e", 'tell application "Terminal" to activate'],
                       check=True, capture_output=True)
        return {"opened": True, "command": cmd}
    return {"opened": False, "command": cmd}


def catalogue() -> dict:
    row = lambda key, label, note: {"key": key, "label": label, "note": note}
    cards = []
    for a in registry.automations():
        cards.append({
            "name": a["name"], "label": a["label"], "description": a.get("description", ""), "folder": a["folder"],
            "department": a.get("department"), "missing_env": registry.missing_env(a), "pulls": [p.get("label", p["run"]) for p in a["pull"]],
            "metrics": [m["key"] for m in a["metrics"]],
            "jobs": [{**row(j["key"], j["label"], j.get("note", "")), "kind": j["kind"]} for j in a["jobs"]],
        })
    with db.read() as con:
        runs = [dict(r) for r in con.execute("SELECT id, automation, job_key, label, kind, status, started_at, ended_at FROM automation_runs ORDER BY id DESC LIMIT 12")]
    return {
        "scripts": [row(k, v[0], v[1]) for k, v in CORE_SCRIPTS.items()],
        "claude": [row(k, v[0], v[1]) for k, v in CORE_CLAUDE.items()]
                  + [row(f"brief:{d['slug']}", f"Brief {d['name']}", "Claude as the department lead: writes its brief.") for d in store.dept_list()],
        "terminal": [row(k, v[0], v[1]) for k, v in CORE_TERMINAL.items()],
        "automations": cards,
        "recent": [j.public(len(j.lines)) for j in sorted(JOBS.values(), key=lambda j: -j.started)[:8]],
        "history": runs,
        "claude_found": bool(claude_bin()),
    }
