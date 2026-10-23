"""Append-only JSONL shadow log; the raw material for future fine-tuning."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .secrets_scan import mask_secrets


class JsonlLogger:
    def __init__(self, directory: Path, enabled: bool = True, store_prompt: bool = True):
        self.directory = directory
        self.enabled = enabled
        self.store_prompt = store_prompt

    def write(self, record: dict) -> None:
        if not self.enabled:
            return
        try:
            now = datetime.now(timezone.utc)
            rec = {"ts": now.isoformat(timespec="seconds"), **record}
            prompt = rec.get("prompt")
            if isinstance(prompt, str):
                rec["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8", "surrogatepass")).hexdigest()
                rec["prompt"] = mask_secrets(prompt) if self.store_prompt else None
            line = json.dumps(rec, ensure_ascii=False) + "\n"
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{now:%Y-%m}.jsonl"
            with path.open("a", encoding="utf-8", errors="backslashreplace") as handle:
                handle.write(line)
        except (OSError, TypeError, ValueError):
            pass
