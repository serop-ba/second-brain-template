#!/usr/bin/env python3
"""Read every CSV in inbox/ (columns: metric,date,value[,note]) and print {"points": [...]}.

Processed files move to done/ so they aren't read twice. `date` may be blank (means today).
Metric keys must already exist (python3 brain.py metric add ...); unknown keys are reported, not created.
"""

import csv
import json
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    points, moved = [], []
    for path in sorted((HERE / "inbox").glob("*.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if not (row.get("metric") or "").strip():
                    continue
                points.append({"metric": row["metric"].strip(), "value": row.get("value"),
                               "date": (row.get("date") or "").strip() or date.today().isoformat(), "note": row.get("note", "")})
        moved.append(path)
    print(json.dumps({"points": points}))
    (HERE / "done").mkdir(exist_ok=True)
    for path in moved:
        shutil.move(str(path), str(HERE / "done" / path.name))


if __name__ == "__main__":
    main()
