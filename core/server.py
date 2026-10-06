"""The console: a local web app over the database.

  python3 brain.py serve [--port 8765] [--no-open]

Serves one page on 127.0.0.1 and a small JSON API. Every API call needs the
per-launch token embedded in the page, so another website open in the same
browser can't call localhost. All writes go through store.py / metrics.py, the
same functions the CLI uses, so the audit trail is identical (actor "console").
Stdlib only.
"""

from __future__ import annotations

import json
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import backup
import db
import graph
import jobs
import metrics
import packs
import refresh
import registry
import seed
import store
import views

PAGE = Path(__file__).resolve().parent / "page"
TOKEN = secrets.token_urlsafe(24)
TYPES = {"js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}

RPC = {fn.__name__: fn for fn in [
    store.profile_set, store.profile_unset,
    store.dept_add, store.dept_update, store.dept_remove, store.dept_brief,
    store.doc_add, store.doc_update, store.doc_remove,
    store.north_star_set, store.year_add, store.goal_update, store.goal_remove,
    store.bet_add, store.bet_update, store.bet_remove,
    store.call_add, store.call_update, store.call_resolve, store.call_remove,
    store.task_add, store.task_update, store.task_toggle, store.task_remove,
    store.decision_add, store.decision_outcome, store.decision_update, store.decision_remove,
    store.log_add, store.inbox_add, store.inbox_file, store.inbox_remove,
    metrics.metric_add, metrics.metric_update, metrics.metric_remove, metrics.point_set, metrics.point_delete,
    store.revert, packs.install_automation, packs.remove_automation, packs.apply_profile,
    seed.load, seed.clear,
]}


def page() -> bytes:
    return (PAGE / "index.html").read_text().replace("__TOKEN__", TOKEN).encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "BrainOS/1"

    def log_message(self, fmt, *args):
        pass

    def send(self, code: int, body, ctype: str = "application/json") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self, api: bool) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):  # blocks DNS rebinding
            self.send(403, {"error": "bad host"})
            return False
        if api and self.headers.get("X-Token") != TOKEN:
            self.send(403, {"error": "bad token: reload the page"})
            return False
        return True

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}") if length else {}

    def fail(self, exc: Exception) -> None:
        if isinstance(exc, LookupError):
            self.send(404, {"error": str(exc)})
        elif isinstance(exc, (store.Error, ValueError, TypeError, sqlite3.DatabaseError)):
            self.send(400, {"error": str(exc)})
        else:
            self.send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self):
        url = urlparse(self.path)
        path, q = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
        if not self.allowed(api=path.startswith("/api/")):
            return
        db.ACTOR.set("console")
        try:
            if path in ("/", "/index.html"):
                self.send(200, page(), "text/html; charset=utf-8")
            elif m := re.fullmatch(r"/static/((?:app|orbit)\.(?:js|css))", path):
                self.send(200, (PAGE / m.group(1)).read_bytes(), TYPES[m.group(1).rsplit(".", 1)[1]])
            elif path == "/api/state":
                self.send(200, views.state())
            elif path == "/api/graph":
                self.send(200, graph.build())
            elif path == "/api/doc":
                self.send(200, {**store.doc_get(q.get("ref", "")), "history": store.history("documents", store.doc_get(q.get("ref", ""))["id"])})
            elif path == "/api/changes":
                self.send(200, store.changes(int(q.get("limit", 100)), q.get("entity"), int(q["id"]) if q.get("id") else None, q.get("actor")))
            elif path == "/api/search":
                self.send(200, store.search(q.get("q", "")))
            elif m := re.fullmatch(r"/api/jobs/(\w+)", path):
                job = jobs.JOBS.get(m.group(1))
                self.send(200, job.public(int(q.get("since", 0)))) if job else self.send(404, {"error": "no such job"})
            else:
                self.send(404, {"error": "not found"})
        except Exception as exc:
            self.fail(exc)

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self.allowed(api=True):
            return
        db.ACTOR.set("console")
        try:
            data = self.body()
            if path == "/api/rpc":
                fn = RPC.get(str(data.get("fn")))
                if not fn:
                    raise LookupError(f"unknown call {data.get('fn')!r}")
                result = fn(**(data.get("args") or {}))
                self.send(200, {"ok": True, "result": result if isinstance(result, (dict, list, int, str, float, type(None))) else None})
            elif path == "/api/run":
                self.send(200, jobs.start_job(str(data.get("key", "")), data.get("prompt"), data.get("arg")).public())
            elif path == "/api/terminal":
                self.send(200, jobs.open_terminal(str(data.get("key", ""))))
            elif path == "/api/backup":
                self.send(200, {"path": str(backup.backup())})
            elif path == "/api/refresh_at":
                at = str(data.get("time") or "")
                if at and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
                    raise ValueError("time must be HH:MM")
                db.meta_set("refresh_at", at)
                self.send(200, {"ok": True})
            elif m := re.fullmatch(r"/api/jobs/(\w+)/stop", path):
                job = jobs.JOBS.get(m.group(1))
                if job and job.proc and job.status == "running":
                    job.stopped = True
                    job.proc.terminate()
                self.send(200, {"ok": True})
            else:
                self.send(404, {"error": "not found"})
        except subprocess.CalledProcessError as exc:
            self.send(400, {"error": f"couldn't open Terminal: {exc}"})
        except Exception as exc:
            self.fail(exc)


def first_run() -> None:
    """A brand-new brain opens on demo data so the console isn't empty; `/init` replaces it."""
    if db.meta_get("initialized") is None and not seed.has_user_data():
        seed.load()
        print("First run: loaded demo data. Run /init in Claude Code to replace it with your business.", flush=True)
    db.meta_set("initialized", "1")


def background() -> None:
    """Daily backup, and the daily refresh if it was scheduled and missed (this machine was off, say)."""
    while True:
        try:
            backup.auto_backup()
            at = db.meta_get("refresh_at")
            if at and refresh.due(at) and not any(j.key == "refresh" and j.status == "running" for j in jobs.JOBS.values()):
                jobs.start_job("refresh")
        except Exception as exc:
            print(f"background check failed: {exc}", file=sys.stderr)
        time.sleep(300)


def main(port: int = 8765, open_browser: bool = True) -> None:
    with db.read():
        pass
    first_run()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"error: port {port} is busy. Is the console already running? Otherwise: python3 brain.py serve --port {port + 1}")
    threading.Thread(target=background, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"Brain OS console → {url}   (Ctrl+C to stop)\nData: {db.db_path()}", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
