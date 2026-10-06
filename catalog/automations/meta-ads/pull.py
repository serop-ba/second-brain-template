#!/usr/bin/env python3
"""Turn Ads Manager CSV exports in exports/ into daily ad metrics. Prints {"points": [...]}.

Export with breakdown "By day" and columns: Day, Amount spent, Impressions, Link clicks, Results.
Column names are matched loosely, so "Amount spent (EUR)" and "Amount Spent" both work.
"""

import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path


def find(headers: list, *needles: str):
    for h in headers:
        low = h.lower()
        if any(n in low for n in needles) and "cost per" not in low:
            return h
    return None


def num(value) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value).replace(",", "")) or 0)
    except ValueError:
        return 0.0


def read(path: Path) -> dict:
    days = defaultdict(lambda: {"spend": 0.0, "results": 0.0, "clicks": 0.0})
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        h = reader.fieldnames or []
        day_c, spend_c, res_c, clk_c = find(h, "day", "date"), find(h, "amount spent", "spend"), find(h, "results"), find(h, "link clicks", "clicks")
        if not spend_c:
            raise SystemExit(f"{path.name}: no 'Amount spent' column. Columns: {', '.join(h)}")
        for row in reader:
            key = (row.get(day_c) or "").strip()[:10] if day_c else date.today().isoformat()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", key):
                continue
            d = days[key]
            d["spend"] += num(row.get(spend_c))
            d["results"] += num(row.get(res_c)) if res_c else 0
            d["clicks"] += num(row.get(clk_c)) if clk_c else 0
    return days


def points(days: dict) -> list:
    out = []
    for day, d in sorted(days.items()):
        out += [{"metric": "ad_spend", "value": round(d["spend"], 2), "date": day}, {"metric": "ad_results", "value": d["results"], "date": day}]
        if d["results"]:
            out.append({"metric": "ad_cost_per_result", "value": round(d["spend"] / d["results"], 2), "date": day})
        if d["clicks"]:
            out.append({"metric": "ad_cpc", "value": round(d["spend"] / d["clicks"], 2), "date": day})
    return out


if __name__ == "__main__":
    merged = {}
    for path in sorted((Path(__file__).parent / "exports").glob("*.csv")):
        merged.update(read(path))  # a later export replaces an earlier one for the same day
    print(json.dumps({"points": points(merged)}))
