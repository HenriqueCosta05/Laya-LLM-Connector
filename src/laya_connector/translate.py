"""Schema + state -> Laya request; Laya answers -> Decision."""
from __future__ import annotations

from dataclasses import dataclass

from .schemas import Schema


@dataclass(frozen=True)
class Decision:
    qid: str
    type: str
    label: str
    value: float
    confidence: float
    low: bool
    runner_up: tuple[str, float] | None = None


def build_request(schema: Schema, state, model: str) -> dict:
    return {"state": state, "questions": schema.questions, "model": model}


def build_batch_request(schema: Schema, states: list, model: str) -> dict:
    return {"states": list(states), "questions": schema.questions, "model": model}


def _short(level_text: str) -> str:
    return level_text.split(":", 1)[0].strip()


def _ranked(probabilities: dict) -> list[tuple[str, float]]:
    return sorted(((str(k), float(v)) for k, v in probabilities.items()), key=lambda kv: kv[1], reverse=True)


def parse_answer(qid: str, answer: dict, threshold: float) -> Decision:
    kind = answer["type"]
    runner_up = None
    if kind == "choice":
        ranked = _ranked(answer["probabilities"])
        label, value = ranked[0]
        if len(ranked) > 1:
            runner_up = ranked[1]
    elif kind == "score":
        legend = answer["legend"]
        ranked = _ranked(answer["probabilities"])
        label, value = _short(legend[ranked[0][0]]), float(answer["score"])
        if len(ranked) > 1:
            runner_up = (_short(legend[ranked[1][0]]), ranked[1][1])
    elif kind == "noul":
        value = float(answer["noul"])
        label = "true" if value >= 0.5 else "false"
    else:
        raise ValueError(f"unknown answer type {kind!r}")
    if "answer_confidence" in answer:
        confidence = float(answer["answer_confidence"])
    elif kind == "noul":
        confidence = max(value, 1.0 - value)
    else:
        confidence = float(answer.get("confidence", 0.0))
    return Decision(qid, kind, label, value, confidence, confidence < threshold, runner_up)


def parse_result(schema: Schema, result: dict) -> dict[str, Decision]:
    answers = result["answers"]
    return {qid: parse_answer(qid, answers[qid], schema.thresholds.get(qid, 0.5))
            for qid in schema.questions if qid in answers}
