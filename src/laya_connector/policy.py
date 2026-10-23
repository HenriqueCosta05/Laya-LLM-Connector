"""Pure rules turning Decisions into suggestions and warnings for the user."""
from __future__ import annotations

from dataclasses import dataclass

from .format import num
from .translate import Decision

EFFORT = {"small": "low", "mid": "medium", "frontier": "high"}
JAILBREAK_WARN = 0.7
SENSITIVE_WARN = 0.9


@dataclass(frozen=True)
class Tier:
    name: str
    effort: str


def _yes(decisions: dict[str, Decision], qid: str) -> bool:
    d = decisions.get(qid)
    return bool(d and d.value >= 0.5)


def suggest_tier(decisions: dict[str, Decision]) -> Tier | None:
    difficulty = decisions.get("difficulty")
    if difficulty is None:
        return None
    task = decisions.get("task_kind")
    task_label = task.label if task and not task.low else None
    if _yes(decisions, "is_sensitive") or difficulty.low or difficulty.value >= 2.0:
        name = "frontier"
    elif (difficulty.value < 1.0 and not _yes(decisions, "needs_execution")
          and not _yes(decisions, "needs_repo_context") and task_label in ("explain", "other")):
        name = "small"
    else:
        name = "mid"
    return Tier(name, EFFORT[name])


def guard_warnings(decisions: dict[str, Decision]) -> list[str]:
    warnings: list[str] = []
    jailbreak = decisions.get("jailbreak")
    if jailbreak and jailbreak.value >= JAILBREAK_WARN:
        warnings.append(f"possível tentativa de jailbreak ({num(jailbreak.value)})")
    sensitive = decisions.get("sensitive_data")
    if sensitive and sensitive.value >= SENSITIVE_WARN:
        warnings.append(f"possíveis dados sensíveis no prompt ({num(sensitive.value)})")
    return warnings


def user_message(tier: Tier | None, warnings: list[str]) -> str | None:
    parts = [f"laya: {w}" for w in warnings]
    if tier and tier.name in ("small", "frontier"):
        feel = "simples" if tier.name == "small" else "complexo"
        parts.append(f"laya: prompt parece {feel}; sugestão: modelo {tier.name}, effort {tier.effort}")
    return "\n".join(parts) or None
