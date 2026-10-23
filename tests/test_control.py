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


def test_tail_log(cfg):
    cfg.log_dir.mkdir(parents=True)
    (cfg.log_dir / "daemon.log").write_text("\n".join(f"l{i}" for i in range(100)), encoding="utf-8")
    assert control.tail_log(cfg, 2) == "l98\nl99"
