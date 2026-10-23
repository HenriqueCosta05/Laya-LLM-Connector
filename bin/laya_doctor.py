# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Diagnose config, schemas, daemon reachability and hook latency."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from laya_connector import config, doctor  # noqa: E402

if __name__ == "__main__":
    sys.exit(1 if doctor.run_checks(config.load(ROOT)) else 0)
