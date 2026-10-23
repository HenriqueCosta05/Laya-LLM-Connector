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
