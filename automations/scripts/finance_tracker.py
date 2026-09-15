#!/usr/bin/env python3
"""Compute trends/deltas from the manually-maintained finance ledger.

Usage: python3 finance_tracker.py

Reads config/finance_log.csv (columns: date,metric,value,note). No external
API needed. Prints a JSON report to stdout and saves a snapshot to output/.
"""

import csv
import sys
from collections import defaultdict

from _common import CONFIG_DIR, emit


def load_ledger() -> list[dict]:
    path = CONFIG_DIR / "finance_log.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def compute_trends(rows: list[dict]) -> dict:
    by_metric = defaultdict(list)
    for row in rows:
        by_metric[row["metric"]].append(row)

    trends = {}
    for metric, entries in by_metric.items():
        entries.sort(key=lambda r: r["date"])
        values = [float(r["value"]) for r in entries]
        trends[metric] = {
            "latest": values[-1],
            "latest_date": entries[-1]["date"],
            "previous": values[-2] if len(values) > 1 else None,
            "change": (values[-1] - values[-2]) if len(values) > 1 else None,
            "history_points": len(values),
        }
    return trends


def main() -> None:
    rows = load_ledger()
    if not rows:
        sys.exit("error: automations/config/finance_log.csv is empty")

    report = {"trends": compute_trends(rows)}
    emit(report, "finance_report")


if __name__ == "__main__":
    main()
