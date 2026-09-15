#!/usr/bin/env python3
"""PreToolUse guardrail for the second brain.

Reads the hook payload on stdin and emits a permission decision:
  deny  -> Claude may never do this; the user can still run it by hand.
  ask   -> the user gets a prompt and decides.
  (none)-> normal permission flow.

Exit code is always 0; the decision travels in the JSON.
"""
import json
import re
import sys

def out(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)

def ok():
    sys.exit(0)

try:
    payload = json.load(sys.stdin)
except Exception:
    ok()

tool = payload.get("tool_name", "")
ti = payload.get("tool_input") or {}

# ---------------------------------------------------------------- secrets ---
# Safe placeholder envs stay readable; real ones never are.
SAFE_ENV = re.compile(r"\.env\.(example|sample|template|dist)$")
SECRET_PATH = re.compile(
    r"(^|/)\.env(\.|$)"
    r"|(^|/)\.netrc$"
    r"|(^|/)\.npmrc$"
    r"|(^|/)\.aws/credentials"
    r"|(^|/)\.ssh/"
    r"|(^|/)id_(rsa|ed25519|ecdsa)"
    r"|\.pem$|\.p12$|\.pfx$|\.keystore$"
    r"|(^|/)(credentials|secrets?)\.(json|ya?ml|toml|ini)$"
    r"|(^|/)service[-_]account.*\.json$",
    re.I,
)

def is_secret(path):
    if not path:
        return False
    p = str(path)
    return bool(SECRET_PATH.search(p)) and not SAFE_ENV.search(p)

SECRET_MSG = (
    "Blocked by project guardrail: this path holds credentials. "
    "Claude never reads or writes secret files. If a value is needed, "
    "paste just that value into the conversation yourself."
)

if tool in ("Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep"):
    for key in ("file_path", "path", "notebook_path", "pattern"):
        if is_secret(ti.get(key)):
            out("deny", SECRET_MSG)

# ------------------------------------------------------- raw/ immutability ---
# raw/ is immutable by schema; the one legal edit is the `ingested:` flag.
if tool == "Write":
    fp = str(ti.get("file_path") or "")
    if re.search(r"(^|/)raw/", fp):
        out("deny",
            "Blocked by project guardrail: raw/ is immutable. Source documents "
            "are never overwritten - write to wiki/ or Output/ instead.")
if tool == "Edit":
    fp = str(ti.get("file_path") or "")
    if re.search(r"(^|/)raw/", fp):
        out("ask",
            "raw/ is immutable except for adding `ingested: true` to frontmatter. "
            "Confirm this edit is only that.")

# ------------------------------------------------------------------- bash ---
if tool not in ("Bash", "BashOutput"):
    ok()

cmd = str(ti.get("command") or "")
if not cmd.strip():
    ok()

flat = " ".join(cmd.split())

# Secrets by way of the shell.
if re.search(r"(^|[\s'\"=/])\.env\b", flat) and not re.search(r"\.env\.(example|sample|template|dist)\b", flat):
    out("deny", SECRET_MSG)
if re.search(r"\b(printenv|env)\b\s*(\||>|$)", flat) or re.search(r"\becho\s+\$[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD)", flat):
    out("deny", "Blocked by project guardrail: dumping environment secrets.")

# Never, under any phrasing.
NEVER = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rR][a-zA-Z]*f|\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*f[a-zA-Z]*[rR]",
     "recursive force delete (rm -rf)"),
    (r"\brm\s+-[a-zA-Z]*\s*/\s*($|\s)", "delete of /"),
    (r"\bsudo\b", "sudo"),
    (r"\bmkfs\b|\bdiskutil\s+erase|\bdd\s+[^|]*of=/dev/", "raw disk write"),
    (r">\s*/dev/(disk|sd|nvme)", "raw disk write"),
    (r"\bcurl\b[^|]*\|\s*(sudo\s+)?(ba)?sh|\bwget\b[^|]*\|\s*(sudo\s+)?(ba)?sh",
     "piping a downloaded script straight into a shell"),
    (r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f(\s|$))", "force push"),
    (r"\bgit\s+(filter-branch|filter-repo)\b|\bgit\s+reflog\s+expire\b", "history rewrite"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (discards uncommitted work)"),
    (r"\bgit\s+clean\b.*-[a-zA-Z]*f", "git clean -f (deletes untracked files)"),
    (r"\bshutdown\b|\breboot\b|\bkillall\s+-9\b", "shutting the machine around"),
    (r":\(\)\s*\{.*\};\s*:", "fork bomb"),
]
for pat, what in NEVER:
    if re.search(pat, flat):
        out("deny",
            f"Blocked by project guardrail: {what}. Claude never runs this. "
            "Run it yourself if you truly want it.")

# Git: reading is free, anything that changes state needs a yes.
GIT_READONLY = re.compile(
    r"^git\s+(-C\s+\S+\s+)?(status|log|diff|show|blame|branch\s+(-l|--list)?\s*$|"
    r"remote(\s+-v)?\s*$|config\s+--get|describe|rev-parse|shortlog|ls-files|"
    r"stash\s+list|tag\s*$)\b"
)
for part in re.split(r"&&|\|\||;|\|", flat):
    part = part.strip()
    if not part.startswith("git "):
        continue
    if GIT_READONLY.match(part):
        continue
    out("ask",
        "Project guardrail: git is read-only for Claude by default. "
        f"Approve this git command explicitly to run it: `{part}`")

# Destructive-ish but sometimes legitimate -> the user decides.
MAYBE = [
    (r"\brm\b", "deleting files"),
    (r"\bmv\b\s+\S+\s+/(?!Users/)", "moving files outside the project"),
    (r"\b(chmod|chown)\b", "changing permissions or ownership"),
    (r"\btruncate\b|>\s*[^\s|&>]+\.(md|json|py|sh)\b", "truncating or overwriting a file in place"),
    (r"\bnpm\s+(install|i)\s+-g\b|\bpip3?\s+install\b|\bbrew\s+(install|uninstall)\b", "installing software"),
    (r"\bcurl\b.*(-X\s*(POST|PUT|DELETE|PATCH)|--data|-d\s)", "sending data to an external service"),
    (r"\bgh\s+(pr|issue|repo|release)\s+(create|merge|close|delete|edit)", "acting on GitHub"),
]
for pat, what in MAYBE:
    if re.search(pat, flat):
        out("ask", f"Project guardrail: {what}. Confirm before this runs.")

ok()
