#!/usr/bin/env python3
"""Pull your YouTube channel's public stats. Prints {"points": [...]} for the brain to record."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


def fetch(channel_id: str, api_key: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/channels?" + urllib.parse.urlencode(
        {"part": "statistics", "id": channel_id, "key": api_key})
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"YouTube API error {exc.code}: {exc.read().decode()[:200]}")


def points(data: dict, day: str) -> list:
    items = data.get("items") or []
    if not items:
        sys.exit("no channel found for that YOUTUBE_CHANNEL_ID (it starts with UC...)")
    stats = items[0]["statistics"]
    return [{"metric": key, "value": int(stats.get(field, 0)), "date": day}
            for key, field in (("youtube_subscribers", "subscriberCount"), ("youtube_views", "viewCount"), ("youtube_videos", "videoCount"))]


if __name__ == "__main__":
    print(json.dumps({"points": points(fetch(os.environ["YOUTUBE_CHANNEL_ID"], os.environ["YOUTUBE_API_KEY"]), date.today().isoformat())}))
