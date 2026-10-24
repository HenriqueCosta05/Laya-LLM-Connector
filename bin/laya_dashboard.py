# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Render the shadow log as a self-contained HTML performance dashboard."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from laya_connector import dashboard  # noqa: E402

if __name__ == "__main__":
    sys.exit(dashboard.main(ROOT, sys.argv[1:]))
