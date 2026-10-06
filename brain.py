#!/usr/bin/env python3
"""Brain OS entry point: `python3 brain.py --help`. Everything lives in core/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    main()
