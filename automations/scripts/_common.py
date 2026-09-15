"""Shared helpers for automation scripts. Not a script itself."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

AUTOMATIONS_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = AUTOMATIONS_DIR / "config"
OUTPUT_DIR = AUTOMATIONS_DIR.parent / "Output" / "analytics"

load_dotenv(AUTOMATIONS_DIR / ".env")


def load_channels_config() -> dict:
    with open(CONFIG_DIR / "channels.yaml") as f:
        return yaml.safe_load(f) or {}


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"error: {name} is not set. Copy automations/.env.example to "
            f"automations/.env and fill it in."
        )
    return value


def write_output(name: str, data: dict) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = OUTPUT_DIR / f"{name}_{stamp}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def latest_output(prefix: str) -> Optional[Path]:
    matches = sorted(OUTPUT_DIR.glob(f"{prefix}_*.json"))
    return matches[-1] if matches else None


def emit(data: dict, output_name: str) -> None:
    """Print JSON to stdout and save a snapshot to output/."""
    path = write_output(output_name, data)
    print(json.dumps(data, indent=2))
    print(f"\nsaved snapshot: {path.relative_to(AUTOMATIONS_DIR.parent)}", file=sys.stderr)
