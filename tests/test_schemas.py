import json

import pytest

from laya_connector.schemas import SchemaError, load_schemas


def test_repo_schemas_load(schemas):
    assert set(schemas) == {"hook", "task_kind", "commit_type", "change_risk", "issue_triage",
                            "source_relevance", "claim_check"}
    hook = schemas["hook"]
    assert hook.state_key == "request" and not hook.classifiable
    assert list(hook.questions) == ["task_kind", "change_risk", "needs_repo_context", "needs_execution",
                                    "difficulty", "is_sensitive", "jailbreak", "sensitive_data"]
    for name in ("task_kind", "commit_type", "change_risk", "issue_triage"):
        assert schemas[name].classifiable and list(schemas[name].questions) == [name]


def test_missing_threshold_defaults_to_half(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps({
        "name": "x", "version": 1, "description": "d", "state_key": "item",
        "questions": {"q": {"type": "noul", "instructions": "i"}}}), encoding="utf-8")
    assert load_schemas(tmp_path)["x"].thresholds == {"q": 0.5}


@pytest.mark.parametrize("bad", [
    {"name": "other", "version": 1, "description": "d", "state_key": "s", "questions": {"q": {"type": "noul", "instructions": "i"}}},
    {"name": "x", "version": 1, "description": "d", "state_key": "s", "questions": {"q": {"type": "bogus", "instructions": "i"}}},
    {"name": "x", "version": 1, "description": "d", "state_key": "s", "questions": {}},
    {"name": "x", "version": 1, "description": "d", "state_key": "s", "questions": {"q": {"type": "noul", "instructions": "i"}},
     "thresholds": {"nope": 0.5}},
    {"name": "x", "version": 1, "description": "d", "state_key": "s", "classifiable": True,
     "questions": {"a": {"type": "noul", "instructions": "i"}}},
])
def test_invalid_schema_raises(tmp_path, bad):
    (tmp_path / "x.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SchemaError):
        load_schemas(tmp_path)
