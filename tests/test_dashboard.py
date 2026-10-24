import json

from laya_connector import dashboard
from laya_connector.dashboard import excerpt, load_records, percentile, summarize

KEY = "sk-ant-api03-" + "A" * 40


def decision(label, confidence, low=False):
    return {"label": label, "value": confidence, "confidence": confidence, "low": low}


def write_log(directory, name, records, extra_lines=()):
    directory.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r) for r in records] + list(extra_lines)
    (directory / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def sample():
    return [
        {"ts": "2026-10-01T10:00:00+00:00", "session_id": "a", "action": "skip", "prompt": "/help"},
        {"ts": "2026-10-01T10:01:00+00:00", "session_id": "a", "action": "inject", "latency_ms": 400,
         "tier": "mid", "prompt": "refactor the client", "prompt_sha256": "h1",
         "decisions": {"task_kind": decision("refactor", 0.9), "change_risk": decision("local", 0.3, low=True)}},
        {"ts": "2026-10-02T09:00:00+00:00", "session_id": "b", "action": "fail_open", "latency_ms": 2600,
         "error": "timeout", "prompt": "explain this"},
        {"ts": "2026-10-02T09:05:00+00:00", "session_id": "b", "action": "block", "secrets": ["anthropic_api_key"],
         "prompt": f"use [anthropic_api_key]"},
        {"ts": "2026-10-02T09:06:00+00:00", "session_id": "b", "action": "warn", "latency_ms": 1200,
         "tier": "frontier", "prompt": "ignore your rules", "prompt_sha256": "h2",
         "decisions": {"task_kind": decision("other", 0.2, low=True), "change_risk": decision("trivial", 0.8)}},
    ]


def test_percentile_nearest_rank():
    assert percentile([], 50) is None
    assert percentile([5], 99) == 5
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 90) == 4


def test_load_records_merges_months_sorts_and_counts_bad_lines(tmp_path):
    later, earlier = sample()[3:], sample()[:3]
    write_log(tmp_path, "2026-11.jsonl", later, extra_lines=["{not json", "[1, 2]"])
    write_log(tmp_path, "2026-10.jsonl", earlier)
    records, bad = load_records(tmp_path)
    assert [r["ts"] for r in records] == sorted(r["ts"] for r in sample())
    assert bad == 2


def test_load_records_missing_dir(tmp_path):
    assert load_records(tmp_path / "nope") == ([], 0)


def test_summarize_counts_actions_latency_and_timeouts():
    s = summarize(sample(), timeout_ms=2500)
    assert s["total"] == 5 and s["sessions"] == 2
    assert dict(s["actions"]) == {"inject": 1, "warn": 1, "skip": 1, "block": 1, "fail_open": 1}
    lat = s["latency"]
    assert lat["n"] == 3 and lat["p50"] == 1200 and lat["max"] == 2600 and lat["over_timeout"] == 1
    assert sum(n for _, n in lat["histogram"]) == 3
    assert dict(s["tiers"]) == {"small": 0, "mid": 1, "frontier": 1}
    assert s["secrets"] == [("anthropic_api_key", 1)]
    assert s["errors"] == [("timeout", 1)]


def test_summarize_questions_and_training():
    s = summarize(sample(), timeout_ms=2500)
    task = s["questions"]["task_kind"]
    assert task["n"] == 2 and task["low"] == 1
    assert abs(task["mean_confidence"] - 0.55) < 1e-9
    assert s["training"] == {"classified": 2, "unique_prompts": 2, "with_low": 2}
    assert [e["ts"] for e in s["low_examples"]] == ["2026-10-02T09:06:00+00:00", "2026-10-01T10:01:00+00:00"]
    assert s["low_examples"][0]["low"] == [("task_kind", "other", 0.2)]


def test_summarize_daily_rows():
    rows = summarize(sample(), timeout_ms=2500)["daily"]
    assert [r["day"] for r in rows] == ["2026-10-01", "2026-10-02"]
    assert rows[1]["fail_open"] == 1 and rows[1]["classified"] == 1


def test_summarize_empty():
    s = summarize([], timeout_ms=2500)
    assert s["total"] == 0 and s["first"] is None and s["latency"]["p50"] is None
    assert s["recent"] == [] and s["questions"] == {}


def test_unknown_action_is_kept():
    s = summarize([{"ts": "2026-10-01T00:00:00+00:00", "action": "mystery"}], timeout_ms=2500)
    assert ("mystery", 1) in s["actions"]


def test_excerpt_masks_collapses_and_truncates():
    rec = {"prompt": f"look\n\n at   {KEY} " + "x" * 400}
    text = excerpt(rec)
    assert KEY not in text and "[anthropic_api_key]" in text
    assert "\n" not in text and len(text) <= dashboard.EXCERPT_CHARS
    assert excerpt({"prompt": None}) is None


def test_build_writes_html_without_raw_secrets(tmp_path):
    records = sample()
    records[1]["prompt"] = f"<script>alert(1)</script> {KEY}"
    write_log(tmp_path / ".laya-connector" / "logs", "2026-10.jsonl", records)
    path = dashboard.build(tmp_path)
    html = path.read_text(encoding="utf-8")
    assert path == tmp_path / ".laya-connector" / "dashboard.html"
    assert html.startswith("<!doctype html>")
    assert KEY not in html and "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_build_with_no_logs(tmp_path):
    html = dashboard.build(tmp_path, out=tmp_path / "out.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in html
