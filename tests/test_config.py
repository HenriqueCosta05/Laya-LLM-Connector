import tomllib

from laya_connector import config


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_defaults_without_files(tmp_path):
    cfg = config.load(tmp_path, env={})
    assert cfg.daemon_url == "http://127.0.0.1:8000"
    assert cfg.checkpoint == "multilingual"
    assert cfg.remote_key is None
    assert cfg.log_dir == tmp_path / ".laya-connector" / "logs"
    assert cfg.schemas_dir == tmp_path / "schemas"


def test_layering_config_local_secrets_env(tmp_path):
    write(tmp_path / config.CONFIG_FILE, '[daemon]\nport = 9000\ndevice = "cuda"\n[hook]\ntimeout = 1.5\n')
    write(tmp_path / config.LOCAL_FILE, '[daemon]\ndevice = "cpu"\ntrusted_local = ["10.0.0.0/8"]\n')
    write(tmp_path / config.STATE_DIR / config.SECRETS_FILE, '[secrets]\nremote_key = "k1"\n')
    cfg = config.load(tmp_path, env={"LAYA_CONNECTOR_DAEMON_URL": "http://h:1", "LAYA_CONNECTOR_LOG_ENABLED": "0"})
    assert cfg.port == 9000
    assert cfg.device == "cpu"
    assert cfg.trusted_local == ("10.0.0.0/8",)
    assert cfg.hook_timeout == 1.5
    assert cfg.remote_key == "k1"
    assert cfg.daemon_url == "http://h:1"
    assert cfg.log_enabled is False


def test_repo_defaults_file_parses():
    from tests.conftest import REPO
    cfg = config.load(REPO, env={})
    assert cfg.port == 8000 and cfg.mcp_max_items == 128


def test_update_toml_file_round_trip(tmp_path):
    path = tmp_path / "x" / "local.toml"
    config.update_toml_file(path, "daemon", "device", "cpu")
    config.update_toml_file(path, "daemon", "trusted_local", ["1.2.3.4/32"])
    config.update_toml_file(path, "log", "enabled", False)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data == {"daemon": {"device": "cpu", "trusted_local": ["1.2.3.4/32"]}, "log": {"enabled": False}}
