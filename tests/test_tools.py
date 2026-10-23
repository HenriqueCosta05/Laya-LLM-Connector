from laya_connector import tools
from laya_connector.client import DaemonClient
from tests import answers as A


def batch_responder(answer_for):
    """answer_for(state) -> answer dict for the schema's only question id."""
    def respond(method, path, body):
        qid = next(iter(body["questions"]))
        return 200, {"results": [A.result(**{qid: answer_for(s)}) for s in body["states"]]}
    return respond


def client(fake):
    return DaemonClient(fake.url, timeout=5)


def test_classify_items(cfg, fake_daemon, schemas):
    fake_daemon.responder = batch_responder(
        lambda s: A.choice({"fix": 0.9, "feat": 0.1}) if "bug" in s["item"] else A.choice({"feat": 0.45, "chore": 0.4, "fix": 0.15}))
    out = tools.classify(cfg, client(fake_daemon), schemas, "commit_type", items=["fix bug in login", "add export"])
    assert out == "commit_type n=2 low=1\n1 fix .90\n2 ? feat .45 / chore .40"
    assert fake_daemon.requests[0][3]["model"] == "multilingual"


def test_classify_paths_reads_files_locally(cfg, fake_daemon, schemas):
    (cfg.root / "a.txt").write_text("fix bug", encoding="utf-8")
    fake_daemon.responder = batch_responder(lambda s: A.choice({"fix": 0.9, "feat": 0.1}))
    out = tools.classify(cfg, client(fake_daemon), schemas, "commit_type", paths=["*.txt"])
    assert out == "commit_type n=1 low=0\na.txt fix .90"
    assert fake_daemon.requests[0][3]["states"] == [{"item": "fix bug"}]


def test_classify_chunks_batches_of_64(make_cfg, fake_daemon, schemas):
    cfg = make_cfg(mcp_max_items=200)
    fake_daemon.responder = batch_responder(lambda s: A.choice({"fix": 0.9, "feat": 0.1}))
    tools.classify(cfg, client(fake_daemon), schemas, "commit_type", items=[f"c{i}" for i in range(130)])
    assert [len(r[3]["states"]) for r in fake_daemon.requests] == [64, 64, 2]


def test_classify_input_errors(cfg, fake_daemon, schemas):
    c = client(fake_daemon)
    assert tools.classify(cfg, c, schemas, "nope", items=["x"]).startswith("laya: error: unknown schema 'nope'; valid: ")
    assert tools.classify(cfg, c, schemas, "hook", items=["x"]).startswith("laya: error: unknown schema")
    assert tools.classify(cfg, c, schemas, "commit_type") == "laya: error: pass exactly one of items, paths, lines"
    assert tools.classify(cfg, c, schemas, "commit_type", lines={"file": "../x"}).startswith("laya: error: refused")
    assert fake_daemon.requests == []


def test_classify_unavailable(cfg, schemas):
    out = tools.classify(cfg, DaemonClient("http://127.0.0.1:9", timeout=1), schemas, "commit_type", items=["x"])
    assert out.startswith("laya: unavailable (")


def test_filter_sources(cfg, fake_daemon, schemas):
    probs = {"a": 0.91, "b": 0.2, "c": 0.62}
    fake_daemon.responder = batch_responder(lambda s: A.noul(probs[s["passage"]]))
    srcs = [{"id": "s1", "text": "a"}, {"id": "s2", "text": "b"}, {"id": "s3", "text": "c"}]
    assert tools.filter_sources(cfg, client(fake_daemon), schemas, "q?", sources=srcs) == "keep 2/3: s1 .91, s3 .62"
    assert tools.filter_sources(cfg, client(fake_daemon), schemas, "q?", sources=srcs, top_k=1) == "keep 1/3: s1 .91"
    assert fake_daemon.requests[0][3]["states"][0] == {"query": "q?", "passage": "a"}


def test_check_claim(cfg, fake_daemon, schemas):
    rel = {"x": {"entails": 0.88, "contradicts": 0.02, "neutral": 0.1},
           "y": {"entails": 0.1, "contradicts": 0.1, "neutral": 0.8}}
    fake_daemon.responder = batch_responder(lambda s: A.choice(rel[s["passage"]]))
    out = tools.check_claim(cfg, client(fake_daemon), schemas, "the sky is blue",
                            passages=[{"id": "p1", "text": "x"}, {"id": "p2", "text": "y"}])
    assert out == "supported: 1 entail, 0 contradict, 1 neutral\np1 entails .88"


def test_instructions_are_short_and_list_schemas(schemas):
    text = tools.instructions(schemas)
    for name in tools.classifiable_names(schemas):
        assert name in text
    assert "[laya]" in text and "paths" in text and len(text.split()) < 140
    assert "repo_ctx" in text and "run_tests" in text and "risk=" in text


def short_responder(answer):
    def respond(method, path, body):
        qid = next(iter(body["questions"]))
        return 200, {"results": [A.result(**{qid: answer}) for _ in body["states"][:-1]]}
    return respond


def test_short_daemon_results_are_an_error(cfg, fake_daemon, schemas):
    c = client(fake_daemon)
    srcs = [{"id": "s1", "text": "a"}, {"id": "s2", "text": "b"}]
    fake_daemon.responder = short_responder(A.choice({"fix": 0.9, "feat": 0.1}))
    out = tools.classify(cfg, c, schemas, "commit_type", items=["a", "b"])
    assert out.startswith("laya: error: bad daemon answer:")
    fake_daemon.responder = short_responder(A.noul(0.9))
    assert tools.filter_sources(cfg, c, schemas, "q?", sources=srcs).startswith("laya: error: bad daemon answer:")
    fake_daemon.responder = short_responder(A.choice({"entails": 0.9, "contradicts": 0.05, "neutral": 0.05}))
    assert tools.check_claim(cfg, c, schemas, "c", passages=srcs).startswith("laya: error: bad daemon answer:")


def test_filter_sources_non_positive_top_k_means_no_limit(cfg, fake_daemon, schemas):
    fake_daemon.responder = batch_responder(lambda s: A.noul(0.9))
    srcs = [{"id": "s1", "text": "a"}, {"id": "s2", "text": "b"}]
    for k in (-1, 0):
        assert tools.filter_sources(cfg, client(fake_daemon), schemas, "q?", sources=srcs, top_k=k).startswith("keep 2/2")


def test_bad_lines_argument_types_return_error_text(cfg, fake_daemon, schemas):
    (cfg.root / "log.txt").write_text("a\nb\n", encoding="utf-8")
    c = client(fake_daemon)
    for lines in ({"file": "log.txt", "from": "1", "to": "x"}, "not-a-dict"):
        out = tools.classify(cfg, c, schemas, "commit_type", lines=lines)
        assert out.startswith("laya: error: ")
    assert fake_daemon.requests == []


def test_missing_named_schema_returns_error_text(cfg, fake_daemon):
    c = client(fake_daemon)
    assert tools.filter_sources(cfg, c, {}, "q", sources=[{"id": "1", "text": "t"}]).startswith("laya: error: ")
    assert tools.check_claim(cfg, c, {}, "c", passages=[{"id": "1", "text": "t"}]).startswith("laya: error: ")
