#!/usr/bin/env python3
"""Starting point for a new automation. Copy this folder to automations/<name>/ (or ask Claude: /connect).

A pull prints one JSON object on stdout:

  {"points": [{"metric": "mrr", "value": 1200, "date": "2026-10-05"}]}

`metric` is a key that exists in the brain (python3 brain.py metric add ...). `date` is optional (default today).
Print logs to stderr. Exit non-zero with a message on failure: the refresh keeps the last real value.
Secrets come from environment variables listed in automation.json `env` (they live in automations/.env).
"""

import json
import os
import sys
from datetime import date


def fetch() -> float:
    key = os.environ["MY_API_KEY"]
    # Call the API with urllib.request, parse the response, return the number.
    raise NotImplementedError(f"replace this with a call that uses {key[:2]}...")


if __name__ == "__main__":
    try:
        value = fetch()
    except NotImplementedError as exc:
        sys.exit(str(exc))
    print(json.dumps({"points": [{"metric": "my_metric", "value": value, "date": date.today().isoformat()}]}))
