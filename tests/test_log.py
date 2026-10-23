import hashlib
import json

from laya_connector.log import JsonlLogger

KEY = "sk-ant-api03-" + "A" * 40


def read_all(directory):
    files = list(directory.glob("*.jsonl"))
    assert len(files) == 1
    return [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]


def test_writes_masked_prompt_and_hash(tmp_path):
    logger = JsonlLogger(tmp_path / "logs")
    prompt = f"use {KEY}"
    logger.write({"action": "block", "prompt": prompt})
    (rec,) = read_all(tmp_path / "logs")
    assert rec["action"] == "block" and KEY not in rec["prompt"]
    assert rec["prompt_sha256"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert "ts" in rec


def test_store_prompt_false_keeps_only_hash(tmp_path):
    JsonlLogger(tmp_path, store_prompt=False).write({"prompt": "hello world"})
    (rec,) = read_all(tmp_path)
    assert rec["prompt"] is None and rec["prompt_sha256"]


def test_disabled_writes_nothing(tmp_path):
    JsonlLogger(tmp_path / "logs", enabled=False).write({"x": 1})
    assert not (tmp_path / "logs").exists()


def test_never_raises_on_unwritable_dir(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    JsonlLogger(blocker / "logs").write({"x": 1})   # parent is a file: mkdir fails, must not raise
