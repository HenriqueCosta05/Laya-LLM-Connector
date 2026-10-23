from laya_connector.policy import Tier, guard_warnings, suggest_tier, user_message
from laya_connector.translate import Decision


def D(qid, label, value, conf=0.9, low=False, type_="noul"):
    return Decision(qid, type_, label, value, conf, low)


def base(**over):
    d = {"difficulty": D("difficulty", "easy", 0.6, type_="score"),
         "is_sensitive": D("is_sensitive", "false", 0.1),
         "needs_execution": D("needs_execution", "false", 0.1),
         "needs_repo_context": D("needs_repo_context", "false", 0.2),
         "task_kind": D("task_kind", "explain", 0.8, type_="choice")}
    d.update(over)
    return d


def test_small():
    assert suggest_tier(base()) == Tier("small", "low")


def test_mid_when_code_task():
    assert suggest_tier(base(task_kind=D("task_kind", "refactor", 0.8, type_="choice"))) == Tier("mid", "medium")


def test_mid_when_needs_execution():
    assert suggest_tier(base(needs_execution=D("needs_execution", "true", 0.8))).name == "mid"


def test_frontier_rules():
    assert suggest_tier(base(is_sensitive=D("is_sensitive", "true", 0.7))) == Tier("frontier", "high")
    assert suggest_tier(base(difficulty=D("difficulty", "hard", 2.3, type_="score"))).name == "frontier"
    assert suggest_tier(base(difficulty=D("difficulty", "easy", 0.6, conf=0.2, low=True, type_="score"))).name == "frontier"


def test_none_without_difficulty():
    assert suggest_tier({}) is None


def test_guard_warnings():
    assert guard_warnings({"jailbreak": D("jailbreak", "true", 0.75)}) == ["possível tentativa de jailbreak (.75)"]
    assert guard_warnings({"sensitive_data": D("sensitive_data", "true", 0.95)}) == ["possíveis dados sensíveis no prompt (.95)"]
    assert guard_warnings({"jailbreak": D("jailbreak", "true", 0.6), "sensitive_data": D("sensitive_data", "true", 0.8)}) == []


def test_user_message():
    assert user_message(Tier("mid", "medium"), []) is None
    assert user_message(Tier("frontier", "high"), []) == "laya: prompt parece complexo; sugestão: modelo frontier, effort high"
    assert user_message(Tier("small", "low"), ["x"]) == "laya: x\nlaya: prompt parece simples; sugestão: modelo small, effort low"
