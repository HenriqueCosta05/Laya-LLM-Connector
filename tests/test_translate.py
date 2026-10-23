from laya_connector.translate import Decision, build_batch_request, build_request, parse_answer, parse_result
from tests import answers as A

RISK = ["trivial: a", "local: b", "cross-module: c", "breaking: d"]


def test_build_request_pins_model(schemas):
    payload = build_request(schemas["hook"], {"request": "hi"}, "multilingual")
    assert payload == {"state": {"request": "hi"}, "questions": schemas["hook"].questions, "model": "multilingual"}


def test_build_batch_request(schemas):
    payload = build_batch_request(schemas["commit_type"], [{"item": "a"}, {"item": "b"}], "multilingual")
    assert payload["states"] == [{"item": "a"}, {"item": "b"}] and payload["model"] == "multilingual"


def test_parse_choice_with_runner_up():
    d = parse_answer("q", A.choice({"fix": 0.6, "feat": 0.3, "docs": 0.1}), threshold=0.5)
    assert d == Decision("q", "choice", "fix", 0.6, 0.6, False, ("feat", 0.3))


def test_parse_choice_low_confidence():
    assert parse_answer("q", A.choice({"fix": 0.45, "feat": 0.4, "docs": 0.15}), threshold=0.5).low is True


def test_parse_score_uses_short_level_and_expected_value():
    d = parse_answer("r", A.score([0.05, 0.15, 0.5, 0.3], RISK), threshold=0.4)
    assert d.label == "cross-module" and d.runner_up == ("breaking", 0.3)
    assert abs(d.value - 2.05) < 1e-9 and d.confidence == 0.5 and not d.low


def test_parse_noul_without_answer_confidence():
    d = parse_answer("n", {"type": "noul", "noul": 0.2}, threshold=0.7)
    assert (d.label, d.value, d.confidence, d.low) == ("false", 0.2, 0.8, False)


def test_parse_result_keeps_schema_order_and_thresholds(schemas):
    res = A.result(task_kind=A.choice({"refactor": 0.82, "bugfix": 0.18}), jailbreak=A.noul(0.55))
    decisions = parse_result(schemas["hook"], res)
    assert list(decisions) == ["task_kind", "jailbreak"]
    assert decisions["jailbreak"].low is True   # max(.55,.45)=.55 < hook threshold .6
