# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Usage: uv run --script bin/laya_daemon.py start|stop|status|logs"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from laya_connector import config, control  # noqa: E402

COMMANDS = {"start": control.start, "stop": control.stop, "status": control.status, "logs": control.tail_log}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    print(COMMANDS[sys.argv[1]](config.load(ROOT)))
