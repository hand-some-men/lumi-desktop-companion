"""Test configuration: make the tools directory importable."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "tools", ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
