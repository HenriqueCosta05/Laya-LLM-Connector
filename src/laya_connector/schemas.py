"""Named, versioned Laya question sets. Claude only ever sees the names."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

QUESTION_TYPES = {"choice", "score", "noul"}


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Schema:
    name: str
    version: int
    description: str
    state_key: str
    questions: dict[str, dict]
    thresholds: dict[str, float]
    classifiable: bool


def _parse(path: Path) -> Schema:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data.get("name")
    if name != path.stem:
        raise SchemaError(f"{path.name}: name {name!r} must match the file name")
    questions = data.get("questions") or {}
    if not questions:
        raise SchemaError(f"{path.name}: no questions")
    for qid, question in questions.items():
        if question.get("type") not in QUESTION_TYPES or not question.get("instructions"):
            raise SchemaError(f"{path.name}: question {qid!r} needs a valid type and instructions")
    thresholds = {qid: 0.5 for qid in questions}
    extra = set(data.get("thresholds", {})) - set(questions)
    if extra:
        raise SchemaError(f"{path.name}: thresholds for unknown questions {sorted(extra)}")
    thresholds.update({qid: float(v) for qid, v in data.get("thresholds", {}).items()})
    classifiable = bool(data.get("classifiable", False))
    if classifiable and list(questions) != [name]:
        raise SchemaError(f"{path.name}: a classifiable schema has one question named like the schema")
    return Schema(name=name, version=int(data["version"]), description=str(data["description"]),
                  state_key=str(data["state_key"]), questions=questions, thresholds=thresholds,
                  classifiable=classifiable)


def load_schemas(directory: Path) -> dict[str, Schema]:
    return {schema.name: schema for schema in map(_parse, sorted(directory.glob("*.json")))}
