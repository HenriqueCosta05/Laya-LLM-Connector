"""Start/stop/status for the background daemon, on POSIX and Windows."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .client import DaemonClient, DaemonError
from .config import Config


def venv_python(root: Path) -> Path:
    venv = root / ".venv-daemon"
    return venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"


def _pid_file(cfg: Config) -> Path:
    return cfg.state_dir / "daemon.pid"


def read_pid(cfg: Config) -> int | None:
    try:
        return int(_pid_file(cfg).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie child still answers kill(0); reap it if it is ours.
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        return reaped == 0
    except ChildProcessError:
        return True


def _default_health(cfg: Config):
    client = DaemonClient(cfg.daemon_url, cfg.remote_key, timeout=2)

    def check() -> bool:
        try:
            return client.health().get("status") == "ok"
        except DaemonError:
            return False
    return check


def start(cfg: Config, command: list[str] | None = None, wait_s: float = 180.0, health=None) -> str:
    pid = read_pid(cfg)
    if pid and is_alive(pid):
        return f"daemon already running (pid {pid})"
    if command is None:
        python = venv_python(cfg.root)
        if not python.exists():
            return "daemon venv missing: run `uv run --script bin/laya_setup.py` first"
        command = [str(python), "-m", "laya_connector.daemon"]
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(cfg.root / "src"), "LAYA_CONNECTOR_ROOT": str(cfg.root)}
    kwargs: dict = {"start_new_session": True}
    if os.name == "nt":
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
    with (cfg.log_dir / "daemon.log").open("ab") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                cwd=cfg.root, env=env, **kwargs)
    _pid_file(cfg).write_text(str(proc.pid), encoding="utf-8")
    check = health or _default_health(cfg)
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return f"daemon exited with code {proc.returncode}; see .laya-connector/logs/daemon.log"
        if check():
            return f"daemon started (pid {proc.pid}) at {cfg.daemon_url}"
        time.sleep(0.5)
    return f"daemon (pid {proc.pid}) did not become healthy in {wait_s:.0f}s; see .laya-connector/logs/daemon.log"


def stop(cfg: Config) -> str:
    pid = read_pid(cfg)
    if not pid or not is_alive(pid):
        _pid_file(cfg).unlink(missing_ok=True)
        return "daemon not running"
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not is_alive(pid):
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)
    _pid_file(cfg).unlink(missing_ok=True)
    return f"daemon stopped (pid {pid})"


def status(cfg: Config) -> str:
    pid = read_pid(cfg)
    try:
        health = DaemonClient(cfg.daemon_url, cfg.remote_key, timeout=3).health()
    except DaemonError as exc:
        return f"daemon unreachable at {cfg.daemon_url} ({exc.kind}); pid file: {pid or 'none'}"
    return (f"daemon up at {cfg.daemon_url} pid={pid or '?'} device={health.get('device', '?')} "
            f"loaded={','.join(health.get('loaded', [])) or '-'}")


def tail_log(cfg: Config, lines: int = 50) -> str:
    path = cfg.log_dir / "daemon.log"
    if not path.is_file():
        return "no daemon log yet"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
