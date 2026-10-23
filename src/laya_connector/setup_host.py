"""Idempotent setup of the daemon host: venv, torch (GPU probe -> CPU fallback), laya, key, model."""
from __future__ import annotations

import os
import secrets
import subprocess

from . import config
from .control import venv_python

LAYA_REQUIREMENT = "laya[serve]==0.4.13"
DAEMON_PYTHON = "3.12"
PROBE = (
    "import torch\n"
    "d = 'cuda' if torch.cuda.is_available() else "
    "('mps' if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available() else 'cpu')\n"
    "x = torch.ones(8, device=d)\n"
    "print(d if float((x * 2).sum()) == 16.0 else 'bad')\n"
)
WARMUP = "from laya.serve import build_router; build_router()"


def setup(cfg: config.Config, runner=subprocess.run, uv: str = "uv", say=print) -> int:
    python = venv_python(cfg.root)

    def step(title: str, cmd: list[str], env: dict | None = None) -> bool:
        say(f"-> {title}")
        done = runner(cmd, capture_output=True, text=True, cwd=cfg.root, env=env)
        if done.returncode != 0:
            say(f"[!!] {title} failed:\n{(done.stderr or done.stdout)[-2000:]}")
            return False
        return True

    def probe() -> str | None:
        done = runner([str(python), "-c", PROBE], capture_output=True, text=True, cwd=cfg.root)
        out = (done.stdout or "").strip()
        return out if done.returncode == 0 and out in ("cuda", "mps", "xpu", "cpu") else None

    if not python.exists() and not step("create .venv-daemon",
                                        [uv, "venv", ".venv-daemon", "--python", DAEMON_PYTHON]):
        return 1
    if not step("install torch (auto backend)",
                [uv, "pip", "install", "--python", str(python), "--torch-backend=auto", "torch"]):
        return 1
    device = probe()
    if device is None:
        say("GPU probe failed; falling back to CPU torch")
        if not step("install torch (cpu)", [uv, "pip", "install", "--python", str(python), "--torch-backend=cpu",
                                            "--reinstall-package", "torch", "torch"]):
            return 1
        device = probe()
        if device is None:
            say("[!!] torch does not run on this host")
            return 1
        config.update_toml_file(cfg.local_path, "daemon", "device", "cpu")
    say(f"torch device: {device}")
    if not step(f"install {LAYA_REQUIREMENT}", [uv, "pip", "install", "--python", str(python), LAYA_REQUIREMENT]):
        return 1

    if not cfg.remote_key and not _existing_key(cfg):
        config.update_toml_file(cfg.secrets_path, "secrets", "remote_key", secrets.token_urlsafe(32))
        if os.name != "nt":
            os.chmod(cfg.secrets_path, 0o600)
        say("generated remote_key in .laya-connector/secrets.toml")

    effective = config.load(cfg.root)
    warm_env = {**os.environ, "LAYA_MODELS": effective.checkpoint, "LAYA_PRELOAD": "1", "LAYA_MAX_LOADED": "1"}
    if effective.device:
        warm_env["LAYA_DEVICE"] = effective.device
    if not step(f"download and load checkpoint '{effective.checkpoint}'", [str(python), "-c", WARMUP], env=warm_env):
        return 1
    say("setup complete: start the daemon with `uv run --script bin/laya_daemon.py start`")
    return 0


def _existing_key(cfg: config.Config) -> bool:
    return bool(config.load(cfg.root).remote_key)
