# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Set up this machine as a Laya daemon host (idempotent). Usage: uv run --script bin/laya_setup.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from laya_connector import config, setup_host  # noqa: E402

if __name__ == "__main__":
    sys.exit(setup_host.setup(config.load(ROOT)))
