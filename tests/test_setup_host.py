import subprocess
import tomllib

from laya_connector import setup_host


class FakeRunner:
    def __init__(self, probe_outputs):
        self.calls = []
        self.probe_outputs = list(probe_outputs)

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if "-c" in cmd and setup_host.PROBE in cmd:
            code, out = self.probe_outputs.pop(0)
            return subprocess.CompletedProcess(cmd, code, stdout=out, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def joined(runner):
    return [" ".join(map(str, c)) for c in runner.calls]


def test_gpu_ok_keeps_auto_device(cfg):
    runner = FakeRunner([(0, "cuda\n")])
    assert setup_host.setup(cfg, runner=runner, say=lambda *_: None) == 0
    cmds = joined(runner)
    assert any("venv" in c and ".venv-daemon" in c for c in cmds)
    assert any("--torch-backend=auto" in c for c in cmds)
    assert any(setup_host.LAYA_REQUIREMENT in c for c in cmds)
    assert not any("--torch-backend=cpu" in c for c in cmds)
    assert not cfg.local_path.exists()


def test_gpu_failure_falls_back_to_cpu(cfg):
    runner = FakeRunner([(1, ""), (0, "cpu\n")])
    assert setup_host.setup(cfg, runner=runner, say=lambda *_: None) == 0
    assert any("--torch-backend=cpu" in c for c in joined(runner))
    assert tomllib.loads(cfg.local_path.read_text(encoding="utf-8"))["daemon"]["device"] == "cpu"


def test_remote_key_generated_once(cfg):
    setup_host.setup(cfg, runner=FakeRunner([(0, "cpu\n")]), say=lambda *_: None)
    first = tomllib.loads(cfg.secrets_path.read_text(encoding="utf-8"))["secrets"]["remote_key"]
    setup_host.setup(cfg, runner=FakeRunner([(0, "cpu\n")]), say=lambda *_: None)
    second = tomllib.loads(cfg.secrets_path.read_text(encoding="utf-8"))["secrets"]["remote_key"]
    assert first == second and len(first) >= 32


def test_failed_step_stops_with_nonzero(cfg):
    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
    assert setup_host.setup(cfg, runner=runner, say=lambda *_: None) != 0
