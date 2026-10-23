from laya_connector.format import (classify_block, claim_block, filter_line, hook_line, num, unavailable)
from laya_connector.translate import Decision


def D(qid, label, value, conf=0.9, low=False, runner_up=None, type_="choice"):
    return Decision(qid, type_, label, value, conf, low, runner_up)


def test_num():
    assert num(0.8234) == ".82" and num(0.0) == ".00" and num(1.0) == "1.00" and num(2.25) == "2.25"


def test_unavailable():
    assert unavailable("timeout") == "laya: unavailable (timeout) — decide without it"


def test_hook_line_full():
    d = {"task_kind": D("task_kind", "refactor", 0.82, conf=0.82),
         "change_risk": D("change_risk", "cross-module", 2.1, conf=0.5, type_="score"),
         "needs_repo_context": D("needs_repo_context", "true", 0.9, type_="noul"),
         "needs_execution": D("needs_execution", "true", 0.8, type_="noul")}
    assert hook_line(d) == "[laya] task=refactor .82 | risk=cross-module | repo_ctx | run_tests"


def test_hook_line_omits_low_and_false():
    d = {"task_kind": D("task_kind", "refactor", 0.4, conf=0.4, low=True),
         "change_risk": D("change_risk", "local", 1.0, type_="score"),
         "needs_repo_context": D("needs_repo_context", "false", 0.1, type_="noul"),
         "needs_execution": D("needs_execution", "true", 0.6, conf=0.6, low=True, type_="noul")}
    assert hook_line(d) == "[laya] risk=local"


def test_hook_line_none_when_nothing_useful():
    assert hook_line({"task_kind": D("task_kind", "x", 0.3, conf=0.3, low=True)}) is None


def test_classify_block():
    rows = [("a.py", D("c", "fix", 0.93, conf=0.93)),
            ("b.py", D("c", "refactor", 0.41, conf=0.41, low=True, runner_up=("chore", 0.33)))]
    assert classify_block("commit_type", rows, skipped=2) == (
        "commit_type n=2 low=1 skipped=2\na.py fix .93\nb.py ? refactor .41 / chore .33")


def test_filter_line():
    assert filter_line([("s4", 0.91), ("s1", 0.84)], total=12) == "keep 2/12: s4 .91, s1 .84"
    assert filter_line([], total=3, skipped=1) == "keep 0/3: none (skipped 1)"


def test_claim_block_verdicts():
    e = ("p1", D("relation", "entails", 0.88, conf=0.88))
    c = ("p2", D("relation", "contradicts", 0.7, conf=0.7))
    n = ("p3", D("relation", "neutral", 0.6, conf=0.6))
    assert claim_block([e, n]) == "supported: 1 entail, 0 contradict, 1 neutral\np1 entails .88"
    assert claim_block([c]).startswith("contradicted:")
    assert claim_block([e, c]).startswith("mixed:")
    assert claim_block([n]) == "unclear: 0 entail, 0 contradict, 1 neutral"
