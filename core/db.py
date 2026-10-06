"""The database: connection, schema, and the audit triggers.

One SQLite file (data/brain.db, override with BRAIN_DB) is the only place the
business is stored. Every audited table gets three triggers that write the
row's before/after JSON into `changes`, so a change is recorded even if
someone edits the file with raw SQL. Python writes go through write(), which
tells the triggers who is acting and why. Stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path

CORE = Path(__file__).resolve().parent
ROOT = CORE.parent
SCHEMA_VERSION = 1

# Tables whose every change is recorded. Each has an integer `id`.
AUDITED = [
    "profile", "departments", "documents", "goals", "bets", "items", "open_calls",
    "decisions", "log_entries", "inbox", "metrics", "metric_points",
]
# Deletion order for a full wipe (children first).
WIPE_ORDER = [
    "metric_points", "items", "log_entries", "decisions", "open_calls", "inbox",
    "documents", "bets", "goals", "metrics", "departments", "profile",
]

_ready: set[str] = set()
ACTOR: ContextVar[str | None] = ContextVar("brain_actor", default=None)


def db_path() -> Path:
    return Path(os.environ.get("BRAIN_DB") or ROOT / "data" / "brain.db")


def today() -> str:
    return date.today().isoformat()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def actor() -> str:
    """Who is acting: the console/seed (ACTOR), else BRAIN_ACTOR, else 'claude' inside Claude Code, else 'user'."""
    return ACTOR.get() or os.environ.get("BRAIN_ACTOR") or ("claude" if os.environ.get("CLAUDECODE") else "user")


def _open() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    if str(path) not in _ready:
        con.execute("PRAGMA journal_mode = WAL")
        _ensure_schema(con)
        _ready.add(str(path))
    return con


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]


def _install_triggers(con: sqlite3.Connection) -> None:
    who = "(SELECT actor FROM ctx), (SELECT reason FROM ctx)"
    for table in AUDITED:
        cols = _columns(con, table)
        obj = lambda ref: "json_object(" + ", ".join(f"'{c}', {ref}.{c}" for c in cols) + ")"
        # Pulled metric points would drown the history; only hand-entered ones are audited.
        points = table == "metric_points"
        cond_ins = "NEW.origin = 'manual'" if points else "1"
        cond_del = "OLD.origin = 'manual'" if points else "1"
        cond_upd = "(OLD.origin = 'manual' OR NEW.origin = 'manual')" if points else "1"
        for name in ("ins", "upd", "del"):
            con.execute(f"DROP TRIGGER IF EXISTS audit_{table}_{name}")
        head = "INSERT INTO changes (actor, reason, entity, entity_id, action, {cols}) VALUES ({who}, '{table}', {id}, '{action}', {vals}); END"
        con.execute(
            f"CREATE TRIGGER audit_{table}_ins AFTER INSERT ON {table} WHEN {cond_ins} BEGIN "
            + head.format(cols="after", who=who, table=table, id="NEW.id", action="insert", vals=obj("NEW")))
        con.execute(
            f"CREATE TRIGGER audit_{table}_upd AFTER UPDATE ON {table} "
            f"WHEN {cond_upd} AND {obj('OLD')} IS NOT {obj('NEW')} BEGIN "
            + head.format(cols="before, after", who=who, table=table, id="NEW.id", action="update",
                          vals=f"{obj('OLD')}, {obj('NEW')}"))
        con.execute(
            f"CREATE TRIGGER audit_{table}_del AFTER DELETE ON {table} WHEN {cond_del} BEGIN "
            + head.format(cols="before", who=who, table=table, id="OLD.id", action="delete", vals=obj("OLD")))


def _ensure_schema(con: sqlite3.Connection) -> None:
    has_meta = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
    version = 0
    if has_meta:
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        version = int(row["value"]) if row else 0
    if version >= SCHEMA_VERSION:
        return
    con.executescript((CORE / "schema.sql").read_text())
    _install_triggers(con)
    con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))


@contextmanager
def read():
    con = _open()
    try:
        yield con
    finally:
        con.close()


@contextmanager
def write(reason: str | None = None, who: str | None = None, purge: bool = False):
    """One transaction. The audit triggers record `who` and `reason` for every row touched."""
    con = _open()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE ctx SET actor = ?, reason = ?, purge = ?", (who or actor(), reason, int(purge)))
        yield con
        con.execute("UPDATE ctx SET purge = 0, reason = NULL")
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def meta_get(key: str, default: str | None = None) -> str | None:
    with read() as con:
        row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(key: str, value: str) -> None:
    with write("meta") as con:
        con.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    (key, value))


def die(message: str) -> None:
    sys.exit(f"error: {message}")
