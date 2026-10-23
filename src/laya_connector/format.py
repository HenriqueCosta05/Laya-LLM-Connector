"""Decisions -> the shortest text Claude can act on."""
from __future__ import annotations

from .translate import Decision


def num(x: float) -> str:
    text = f"{x:.2f}"
    return text[1:] if text.startswith("0.") else text


def unavailable(reason: str) -> str:
    return f"laya: unavailable ({reason}) — decide without it"


def _true(decision: Decision | None) -> bool:
    return bool(decision and not decision.low and decision.value >= 0.5)


def hook_line(decisions: dict[str, Decision]) -> str | None:
    parts: list[str] = []
    task = decisions.get("task_kind")
    if task and not task.low:
        parts.append(f"task={task.label} {num(task.confidence)}")
    risk = decisions.get("change_risk")
    if risk and not risk.low:
        parts.append(f"risk={risk.label}")
    for qid, tag in (("needs_repo_context", "repo_ctx"), ("needs_execution", "run_tests")):
        if _true(decisions.get(qid)):
            parts.append(tag)
    return "[laya] " + " | ".join(parts) if parts else None


def classify_block(schema_name: str, rows: list[tuple[str, Decision]], skipped: int = 0) -> str:
    low = sum(1 for _, d in rows if d.low)
    head = f"{schema_name} n={len(rows)} low={low}" + (f" skipped={skipped}" if skipped else "")
    lines = [head]
    for item_id, d in rows:
        if d.low:
            second = f" / {d.runner_up[0]} {num(d.runner_up[1])}" if d.runner_up else ""
            lines.append(f"{item_id} ? {d.label} {num(d.confidence)}{second}")
        else:
            lines.append(f"{item_id} {d.label} {num(d.confidence)}")
    return "\n".join(lines)


def filter_line(kept: list[tuple[str, float]], total: int, skipped: int = 0) -> str:
    body = ", ".join(f"{item_id} {num(p)}" for item_id, p in kept) or "none"
    return f"keep {len(kept)}/{total}: {body}" + (f" (skipped {skipped})" if skipped else "")


def claim_block(rows: list[tuple[str, Decision]], skipped: int = 0) -> str:
    counts = {"entails": 0, "contradicts": 0, "neutral": 0}
    for _, d in rows:
        counts[d.label] = counts.get(d.label, 0) + 1
    entail, contradict = counts["entails"], counts["contradicts"]
    if entail and contradict:
        verdict = "mixed"
    elif entail:
        verdict = "supported"
    elif contradict:
        verdict = "contradicted"
    else:
        verdict = "unclear"
    head = f"{verdict}: {entail} entail, {contradict} contradict, {counts['neutral']} neutral"
    lines = [head + (f", skipped {skipped}" if skipped else "")]
    lines += [f"{item_id} {d.label} {num(d.confidence)}" for item_id, d in rows if d.label != "neutral"]
    return "\n".join(lines)
