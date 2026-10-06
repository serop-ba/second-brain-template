"""Backups: a consistent copy of the database, a readable JSON export, and restore.

  python3 brain.py backup                  # data/backups/brain-<stamp>.db
  python3 brain.py export [--out file]     # all content + history as JSON
  python3 brain.py restore data/backups/brain-....db

The console also makes one backup a day (keeping the newest 14). Stdlib only.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import db
import store


def backup_dir() -> Path:
    return db.db_path().parent / "backups"


def backup(label: str = "") -> Path:
    with db.read():  # make sure the schema exists
        pass
    backup_dir().mkdir(parents=True, exist_ok=True)
    dest = backup_dir() / f"brain-{datetime.now():%Y%m%d-%H%M%S}{'-' + label if label else ''}.db"
    src = sqlite3.connect(db.db_path())
    out = sqlite3.connect(dest)
    try:
        src.backup(out)
        out.execute("PRAGMA journal_mode = DELETE")  # a backup is one self-contained file
    finally:
        out.close()
        src.close()
    return dest


def backups() -> list[Path]:
    return sorted(backup_dir().glob("brain-*.db"), reverse=True) if backup_dir().exists() else []


def auto_backup(keep: int = 14) -> Path | None:
    """One backup per calendar day, pruned to the newest `keep`."""
    stamp = f"brain-{datetime.now():%Y%m%d}"
    if any(p.name.startswith(stamp) for p in backups()):
        return None
    made = backup("daily")
    for old in backups()[keep:]:
        old.unlink(missing_ok=True)
    return made


def export_data() -> dict:
    out: dict = {"exported_at": db.now(), "schema_version": db.SCHEMA_VERSION, "tables": {}}
    with db.read() as con:
        for table in [*db.WIPE_ORDER[::-1], "changes", "automation_runs"]:
            out["tables"][table] = [dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY id")]
        out["meta"] = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}
    return out


def export(path: str | None = None) -> Path:
    dest = Path(path) if path else backup_dir().parent / "export" / f"brain-{datetime.now():%Y%m%d-%H%M%S}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(export_data(), indent=1, ensure_ascii=False))
    return dest


def restore(path: str) -> Path:
    src = Path(path)
    if not src.is_file():
        raise store.Error(f"no such backup: {path}")
    try:
        con = sqlite3.connect(src)
        con.execute("SELECT 1 FROM meta LIMIT 1")
        con.close()
    except sqlite3.DatabaseError:
        raise store.Error(f"{path} is not a Brain OS database") from None
    safety = backup("before-restore")
    target = db.db_path()
    for suffix in ("-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    shutil.copyfile(src, target)
    db._ready.discard(str(target))
    return safety
