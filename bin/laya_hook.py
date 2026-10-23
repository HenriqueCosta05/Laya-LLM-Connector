# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Claude Code UserPromptSubmit hook. Never fails: any error means no output."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    try:
        from laya_connector import config
        from laya_connector.client import DaemonClient
        from laya_connector.hook import handle
        from laya_connector.log import JsonlLogger
        from laya_connector.schemas import load_schemas

        event = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        cfg = config.load(ROOT)
        schema = load_schemas(cfg.schemas_dir)["hook"]
        client = DaemonClient(cfg.daemon_url, cfg.remote_key, timeout=cfg.hook_timeout)
        logger = JsonlLogger(cfg.log_dir, cfg.log_enabled, cfg.log_store_prompt)
        output = handle(event, cfg, client, schema, logger)
    except Exception:
        return 0
    if output:
        sys.stdout.buffer.write(json.dumps(output, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
