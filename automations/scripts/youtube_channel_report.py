#!/usr/bin/env python3
"""Pull current stats for your own YouTube channel(s).

Usage: python3 youtube_channel_report.py

Reads config/channels.yaml -> own_channel.id, requires YOUTUBE_API_KEY.
Prints a JSON report to stdout and saves a snapshot to output/.
"""

import sys

import requests

from _common import emit, load_channels_config, require_env

API_URL = "https://www.googleapis.com/youtube/v3/channels"


def fetch_channel_stats(api_key: str, channel_id: str) -> dict:
    resp = requests.get(
        API_URL,
        params={
            "part": "snippet,statistics",
            "id": channel_id,
            "key": api_key,
        },
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        sys.exit(f"error: no channel found for id {channel_id!r}")
    item = items[0]
    stats = item["statistics"]
    return {
        "id": channel_id,
        "title": item["snippet"]["title"],
        "subscribers": int(stats.get("subscriberCount", 0)),
        "views": int(stats.get("viewCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
    }


def main() -> None:
    api_key = require_env("YOUTUBE_API_KEY")
    config = load_channels_config()
    channel_id = (config.get("own_channel") or {}).get("id")
    if not channel_id:
        sys.exit("error: set own_channel.id in automations/config/channels.yaml")

    report = fetch_channel_stats(api_key, channel_id)
    emit(report, "youtube_channel_report")


if __name__ == "__main__":
    main()
