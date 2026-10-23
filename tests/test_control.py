import json
import os
import sys

from laya_connector import control

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def test_venv_python_layout(tmp_path):
    path = control.venv_python(tmp_path)
    assert path.parent.parent == tmp_path / ".venv-daemon"
    assert path.name in ("python", "python.exe")


def test_start_status_stop_cycle(cfg):
    msg = control.start(cfg, command=SLEEPER, wait_s=5, health=lambda: True)
    assert msg.startswith("daemon started")
    pid = control.read_pid(cfg)
    assert pid and control.is_alive(pid)
    assert control.start(cfg, command=SLEEPER, wait_s=5, health=lambda: True).startswith("daemon already running")
    assert control.stop(cfg) == f"daemon stopped (pid {pid})"
    assert control.read_pid(cfg) is None
    assert control.stop(cfg) == "daemon not running"


def test_start_reports_health_timeout(cfg):
    msg = control.start(cfg, command=SLEEPER, wait_s=0.5, health=lambda: False)
    assert "did not become healthy" in msg
    control.stop(cfg)


def test_start_without_venv_explains_setup(cfg):
    assert "bin/laya_setup.py" in control.start(cfg, wait_s=0.1)


def _write_pid_file(cfg, content):
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    (cfg.state_dir / "daemon.pid").write_text(content, encoding="utf-8")


def test_stop_ignores_recycled_pid(cfg):
    _write_pid_file(cfg, json.dumps({"pid": os.getpid(), "cmd": ["/nonexistent/other", "--other"]}))
    assert control.stop(cfg) == "daemon not running (stale pid file removed)"
    assert control.is_alive(os.getpid())
    assert control.read_pid(cfg) is None


def test_legacy_bare_pid_file_is_stale(cfg):
    _write_pid_file(cfg, str(os.getpid()))
    assert control.read_pid(cfg) == os.getpid()
    assert control.stop(cfg) == "daemon not running (stale pid file removed)"
    assert control.is_alive(os.getpid())
    assert control.read_pid(cfg) is None


def test_start_replaces_stale_pid_file(cfg):
    _write_pid_file(cfg, json.dumps({"pid": os.getpid(), "cmd": ["/nonexistent/other", "--other"]}))
    msg = control.start(cfg, command=SLEEPER, wait_s=5, health=lambda: True)
    try:
        assert msg.startswith("daemon started")
        assert control.read_pid(cfg) != os.getpid()
    finally:
        control.stop(cfg)


def test_tasklist_has_pid_exact_match():
    row_1234 = '"python.exe","1234","Console","1","12,345 K"\n'
    row_123 = '"python.exe","123","Console","1","9,000 K"\n'
    assert control._tasklist_has_pid(row_1234, 123) is False
    assert control._tasklist_has_pid(row_123, 123) is True
    assert control._tasklist_has_pid(row_1234 + row_123, 123) is True
    assert control._tasklist_has_pid('"INFO: No tasks are running which match the specified criteria."\n', 123) is False
    assert control._tasklist_has_pid("", 123) is False


def test_tail_log(cfg):
    cfg.log_dir.mkdir(parents=True)
    (cfg.log_dir / "daemon.log").write_text("\n".join(f"l{i}" for i in range(100)), encoding="utf-8")
    assert control.tail_log(cfg, 2) == "l98\nl99"
