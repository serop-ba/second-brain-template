"""Metrics: definitions with thresholds, one value per day, and verdicts.

A metric is defined once (name, owner department, healthy/watch/bad bands) and
filled either by hand (`metric set`) or by an automation's pull. Nothing is
ever guessed: no value reads `no data`, and bands you haven't set read
`not scored`. Stdlib only.
"""

from __future__ import annotations

import re

import db
import store
from store import Error, _all, _insert, _one, _pick, _update, dept_id

RANGE = re.compile(r"^(-?[\d.]+)\s*(?:-|–|to)\s*(-?[\d.]+)$")
CMP = re.compile(r"^(>=|<=|>|<|=)\s*(-?[\d.]+)$")
KEY = re.compile(r"^[a-z0-9_]+$")
METRIC_FIELDS = ["name", "department", "definition", "unit", "source", "healthy", "watch", "bad", "position"]


def matches(band: str, value: float) -> bool | None:
    """True/False if the band is machine-readable (`>= 500`, `< 200`, `200-499`), None if blank or prose."""
    cell = band.strip().replace(",", "")
    m = RANGE.match(cell)
    if m:
        return float(m.group(1)) <= value <= float(m.group(2))
    m = CMP.match(cell)
    if m:
        target = float(m.group(2))
        return {">=": value >= target, "<=": value <= target, ">": value > target, "<": value < target, "=": value == target}[m.group(1)]
    return None


def check_band(band: str, label: str) -> str:
    band = (band or "").strip()
    if band and matches(band, 0.0) is None:
        raise Error(f"{label} must look like '>= 3000', '<= 3', '1000-2999' (or be blank until you know), got {band!r}")
    return band


def verdict(metric: dict, value: float | None) -> str:
    if value is None:
        return "no data"
    readable = False
    for band in ("healthy", "watch", "bad"):
        result = matches(metric[band], value)
        if result is None:
            continue
        readable = True
        if result:
            return band
    return "no band matches" if readable else "not scored"


def parse_value(value) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        raise Error(f"value must be a number, got {value!r}") from None


def _metric_id(con, key: str) -> int:
    row = con.execute("SELECT id FROM metrics WHERE key = ?", (key,)).fetchone()
    if not row:
        keys = ", ".join(r["key"] for r in con.execute("SELECT key FROM metrics ORDER BY position, id"))
        raise Error(f"no metric {key!r}. Existing: {keys or 'none yet, add one with: metric add'}")
    return row["id"]


def metric_add(key: str, name: str, reason: str | None = None, **fields) -> dict:
    key = key.strip().lower()
    if not KEY.match(key):
        raise Error("the key is lowercase letters, digits and underscores, e.g. mrr or youtube_subscribers")
    if not name.strip():
        raise Error("a metric needs a name")
    data = _pick(fields, [f for f in METRIC_FIELDS if f != "name"])
    for band in ("healthy", "watch", "bad"):
        data[band] = check_band(data.get(band, ""), band)
    with db.write(reason) as con:
        if con.execute("SELECT 1 FROM metrics WHERE key = ?", (key,)).fetchone():
            raise Error(f"metric {key!r} already exists (change it with: metric update {key} ...)")
        data["department_id"] = dept_id(con, data.pop("department", None))
        pos = con.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM metrics").fetchone()[0]
        _insert(con, "metrics", {"key": key, "name": name.strip(), "position": pos, "created_at": db.now(), "updated_at": db.now(), **data})
    return metric_get(key)


def metric_update(key: str, reason: str | None = None, **fields) -> dict:
    data = _pick(fields, METRIC_FIELDS)
    for band in ("healthy", "watch", "bad"):
        if band in data:
            data[band] = check_band(data[band], band)
    with db.write(reason) as con:
        mid = _metric_id(con, key)
        if "department" in data:
            data["department_id"] = dept_id(con, data.pop("department"))
        _update(con, "metrics", mid, {**data, "updated_at": db.now()})
    return metric_get(key)


def metric_remove(key: str, reason: str | None = None) -> None:
    """Deletes the metric and its whole history (both stay in the change log for restore)."""
    with db.write(reason) as con:
        mid = _metric_id(con, key)
        # The cascade is silent to the audit log for pulled points; delete explicitly so each manual point is recorded.
        con.execute("DELETE FROM metric_points WHERE metric_id = ?", (mid,))
        con.execute("DELETE FROM metrics WHERE id = ?", (mid,))


def point_set(key: str, value, date: str | None = None, note: str = "", origin: str = "manual", reason: str | None = None) -> None:
    """Record the value for a day (default today). Same day again replaces it."""
    day = store.check_date(date or db.today())
    num = parse_value(value)
    with db.write(reason) as con:
        _upsert(con, _metric_id(con, key), day, num, origin, note)


def _upsert(con, metric_id: int, day: str, value: float, origin: str, note: str = "") -> bool:
    cur = con.execute("SELECT id, deleted_at, origin FROM metric_points WHERE metric_id = ? AND as_of = ?", (metric_id, day)).fetchone()
    if cur is None:
        _insert(con, "metric_points", {"metric_id": metric_id, "as_of": day, "value": value, "origin": origin, "note": note, "recorded_at": db.now()})
        return True
    if cur["deleted_at"] and origin != "manual":  # a point deleted by hand stays deleted
        return False
    con.execute("UPDATE metric_points SET value = ?, origin = ?, note = ?, recorded_at = ?, deleted_at = NULL WHERE id = ?",
                (value, origin, note, db.now(), cur["id"]))
    return True


def record_points(origin: str, points: list[dict], reason: str | None = None) -> dict:
    """Store what an automation pulled: [{"metric": key, "value": n, "date": "YYYY-MM-DD"?}].
    Unknown keys are reported, never created."""
    recorded, unmapped = 0, []
    with db.write(reason or f"pull: {origin}", who=f"automation:{origin}") as con:
        for p in points:
            row = con.execute("SELECT id FROM metrics WHERE key = ?", (str(p.get("metric", "")),)).fetchone()
            if not row:
                unmapped.append(str(p.get("metric", "")))
                continue
            try:
                value = parse_value(p.get("value"))
                day = store.check_date(p.get("date") or db.today())
            except Error:
                unmapped.append(str(p.get("metric", "")))
                continue
            recorded += _upsert(con, row["id"], day, value, origin, str(p.get("note", "")))
    return {"recorded": recorded, "unmapped": sorted(set(unmapped))}


def point_delete(key: str, date: str, reason: str | None = None) -> None:
    with db.write(reason) as con:
        row = _one(con, "SELECT id, origin FROM metric_points WHERE metric_id = ? AND as_of = ? AND deleted_at IS NULL", _metric_id(con, key), date)
        if not row:
            raise Error(f"no {key} value on {date}")
        if row["origin"] == "manual":
            con.execute("DELETE FROM metric_points WHERE id = ?", (row["id"],))
        else:
            con.execute("UPDATE metric_points SET deleted_at = ? WHERE id = ?", (db.now(), row["id"]))


def metric_get(key: str) -> dict:
    found = [m for m in metric_list() if m["key"] == key]
    if not found:
        raise Error(f"no metric {key!r}")
    return found[0]


def metric_list(with_points: bool = True) -> list[dict]:
    with db.read() as con:
        ms = _all(con, "SELECT m.*, d.slug AS department, d.name AS department_name FROM metrics m LEFT JOIN departments d ON d.id = m.department_id ORDER BY m.position, m.id")
        pts = _all(con, "SELECT metric_id, as_of, value, origin, note FROM metric_points WHERE deleted_at IS NULL ORDER BY metric_id, as_of")
    by: dict[int, list[dict]] = {}
    for p in pts:
        by.setdefault(p["metric_id"], []).append({k: p[k] for k in ("as_of", "value", "origin", "note")})
    for m in ms:
        series = by.get(m["id"], [])
        last = series[-1] if series else None
        prev = series[-2] if len(series) > 1 else None
        m["now"] = last["value"] if last else None
        m["as_of"] = last["as_of"] if last else None
        m["prev"] = prev["value"] if prev else None
        m["delta"] = (last["value"] - prev["value"]) if last and prev else None
        m["verdict"] = verdict(m, m["now"])
        m["days"] = len(series)
        if with_points:
            m["points"] = series
    return ms
