#!/usr/bin/env python3
"""Template for an automation. Copy this, rename it, replace fetch().

Prints one JSON object to stdout and saves a timestamped copy to
Output/analytics/<department>/. Exits non-zero with a clear message if it can't
get real data — never return plausible-looking fake numbers.

Put a department script at automations/scripts/<department>/<name>.py and its
output routes itself; a company-wide script sits directly in scripts/ and
lands in Output/analytics/company/.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()


def find_root(start):
    """Walk up to the repo root. Nesting depth then doesn't matter."""
    for d in start.parents:
        if (d / "CLAUDE.md").exists():
            return d
    sys.exit("could not find the repo root (no CLAUDE.md above this script)")


ROOT = find_root(HERE)

# scripts/marketing/meta_ads.py -> "marketing"; scripts/foo.py -> "company"
DEPARTMENT = HERE.parent.name if HERE.parent.name != "scripts" else "company"
OUT = ROOT / "Output" / "analytics" / DEPARTMENT


def fetch():
    """Replace this. Return a dict of the numbers you care about.

    Return the metrics under the names used in company.md's metrics table —
    that's what lets the dashboard place them without a translation layer.

    Read secrets from the environment (loaded from automations/.env) and fail
    loudly if one is missing:

        key = os.environ.get("SOME_API_KEY")
        if not key:
            sys.exit("SOME_API_KEY not set — add it to automations/.env")
    """
    return {"example_metric": 0}


def main():
    try:
        data = fetch()
    except Exception as e:
        sys.exit(f"{HERE.name} failed: {e}")

    result = {
        "script": HERE.stem,
        "department": DEPARTMENT,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (OUT / f"{result['script']}-{stamp}.json").write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
