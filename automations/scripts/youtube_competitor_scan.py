#!/usr/bin/env python3
"""Pull current stats for tracked competitor channels and diff against the
last snapshot in output/.

Usage: python3 youtube_competitor_scan.py

Reads config/channels.yaml -> competitors, requires YOUTUBE_API_KEY.
Prints a JSON report to stdout and saves a snapshot to output/.
"""

import json
import sys

from youtube_channel_report import fetch_channel_stats

from _common import emit, latest_output, load_channels_config, require_env


def diff_against_last(current: list[dict]) -> list[dict]:
    last_path = latest_output("youtube_competitor_scan")
    if last_path is None:
        for c in current:
            c["delta"] = None
        return current

    last_data = json.loads(last_path.read_text())
    last_by_id = {c["id"]: c for c in last_data.get("competitors", [])}

    for c in current:
        prev = last_by_id.get(c["id"])
        if prev is None:
            c["delta"] = None
            continue
        c["delta"] = {
            "subscribers": c["subscribers"] - prev["subscribers"],
            "views": c["views"] - prev["views"],
            "videos": c["videos"] - prev["videos"],
            "since": last_data.get("generated_at"),
        }
    return current


def main() -> None:
    api_key = require_env("YOUTUBE_API_KEY")
    config = load_channels_config()
    competitors = config.get("competitors") or []
    if not competitors:
        sys.exit("error: add at least one competitor in automations/config/channels.yaml")

    from datetime import datetime, timezone

    results = [fetch_channel_stats(api_key, c["id"]) for c in competitors]
    results = diff_against_last(results)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "competitors": results,
    }
    emit(report, "youtube_competitor_scan")


if __name__ == "__main__":
    main()
