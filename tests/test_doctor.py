from laya_connector.client import DaemonClient
from laya_connector.doctor import run_checks
from tests.conftest import REPO
from tests import answers as A
from laya_connector import config


def test_doctor_all_ok(fake_daemon):
    cfg = config.load(REPO, env={"LAYA_CONNECTOR_DAEMON_URL": fake_daemon.url})

    def respond(method, path, body):
        if path == "/health":
            return 200, {"status": "ok", "device": "cpu", "loaded": ["multilingual"]}
        return 200, A.result(task_kind=A.choice({"refactor": 0.9, "bugfix": 0.1}))
    fake_daemon.responder = respond
    lines = []
    assert run_checks(cfg, DaemonClient(fake_daemon.url, timeout=5), say=lines.append) == 0
    text = "\n".join(lines)
    assert "[ok] schemas" in text and "[ok] daemon" in text and "device=cpu" in text and "[ok] latency" in text


def test_doctor_reports_unreachable():
    cfg = config.load(REPO, env={})
    lines = []
    assert run_checks(cfg, DaemonClient("http://127.0.0.1:9", timeout=1), say=lines.append) == 1
    assert any(l.startswith("[!!] daemon") for l in lines)


def test_doctor_missing_hook_schema(tmp_path):
    (tmp_path / "schemas").mkdir()
    for p in (REPO / "schemas").glob("*.json"):
        if p.stem != "hook":
            (tmp_path / "schemas" / p.name).write_bytes(p.read_bytes())
    cfg = config.load(tmp_path, env={})
    lines = []
    assert run_checks(cfg, DaemonClient("http://127.0.0.1:9", timeout=1), say=lines.append) != 0
    assert any(l.startswith("[!!] schemas") for l in lines)


def test_doctor_non_dict_health(fake_daemon):
    cfg = config.load(REPO, env={})
    fake_daemon.responder = lambda method, path, body: (200, ["nope"])
    lines = []
    assert run_checks(cfg, DaemonClient(fake_daemon.url, timeout=5), say=lines.append) == 1
    assert any(l.startswith("[!!] daemon") for l in lines)


def test_main_reports_malformed_config(tmp_path):
    from laya_connector import doctor
    (tmp_path / "laya-connector.toml").write_text("this is [not toml", encoding="utf-8")
    lines = []
    assert doctor.main(tmp_path, say=lines.append) == 1
    assert any(l.startswith("[!!] config") for l in lines)
