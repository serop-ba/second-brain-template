#!/usr/bin/env python3
"""Template for an automation. Copy this, rename it, replace fetch().

Prints one JSON object to stdout and saves a timestamped copy to
Output/analytics/. Exits non-zero with a clear message if it can't get real
data — never return plausible-looking fake numbers.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Output" / "analytics"


def fetch():
    """Replace this. Return a dict of the numbers you care about.

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
        sys.exit(f"{Path(__file__).name} failed: {e}")

    result = {
        "script": Path(__file__).stem,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (OUT / f"{result['script']}-{stamp}.json").write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
