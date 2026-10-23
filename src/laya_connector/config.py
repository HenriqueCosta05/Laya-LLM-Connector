"""Layered configuration: laya-connector.toml < .local.toml < secrets.toml < env."""
from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = "laya-connector.toml"
LOCAL_FILE = "laya-connector.local.toml"
STATE_DIR = ".laya-connector"
SECRETS_FILE = "secrets.toml"


@dataclass(frozen=True)
class Config:
    root: Path
    daemon_url: str = "http://127.0.0.1:8000"
    host: str = "0.0.0.0"
    port: int = 8000
    device: str = ""
    checkpoint: str = "multilingual"
    trusted_local: tuple[str, ...] = ()
    remote_key: str | None = None
    hook_timeout: float = 2.5
    hook_min_chars: int = 15
    hook_max_chars: int = 4000
    mcp_max_items: int = 128
    mcp_item_chars: int = 2000
    mcp_timeout_base: float = 10.0
    mcp_timeout_per_item: float = 1.0
    log_enabled: bool = True
    log_store_prompt: bool = True

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIR

    @property
    def log_dir(self) -> Path:
        return self.state_dir / "logs"

    @property
    def schemas_dir(self) -> Path:
        return self.root / "schemas"

    @property
    def secrets_path(self) -> Path:
        return self.state_dir / SECRETS_FILE

    @property
    def local_path(self) -> Path:
        return self.root / LOCAL_FILE


_KEYS = {
    ("daemon", "url"): "daemon_url",
    ("daemon", "host"): "host",
    ("daemon", "port"): "port",
    ("daemon", "device"): "device",
    ("daemon", "checkpoint"): "checkpoint",
    ("daemon", "trusted_local"): "trusted_local",
    ("hook", "timeout"): "hook_timeout",
    ("hook", "min_chars"): "hook_min_chars",
    ("hook", "max_chars"): "hook_max_chars",
    ("mcp", "max_items"): "mcp_max_items",
    ("mcp", "item_chars"): "mcp_item_chars",
    ("mcp", "timeout_base"): "mcp_timeout_base",
    ("mcp", "timeout_per_item"): "mcp_timeout_per_item",
    ("log", "enabled"): "log_enabled",
    ("log", "store_prompt"): "log_store_prompt",
    ("secrets", "remote_key"): "remote_key",
}
_ENV = {
    "LAYA_CONNECTOR_DAEMON_URL": "daemon_url",
    "LAYA_CONNECTOR_REMOTE_KEY": "remote_key",
    "LAYA_CONNECTOR_DEVICE": "device",
    "LAYA_CONNECTOR_LOG_ENABLED": "log_enabled",
}
_BOOLS = {"log_enabled", "log_store_prompt"}


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _env_value(attr: str, raw: str):
    if attr in _BOOLS:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return raw


def load(root: Path, env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    values: dict = {}
    layers = (_read(root / CONFIG_FILE), _read(root / LOCAL_FILE), _read(root / STATE_DIR / SECRETS_FILE))
    for data in layers:
        for (section, key), attr in _KEYS.items():
            if key in data.get(section, {}):
                values[attr] = data[section][key]
    for var, attr in _ENV.items():
        if env.get(var):
            values[attr] = _env_value(attr, env[var])
    if "trusted_local" in values:
        values["trusted_local"] = tuple(values["trusted_local"])
    return Config(root=root, **values)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


def dump_toml(data: dict[str, dict]) -> str:
    lines: list[str] = []
    for section, table in data.items():
        lines.append(f"[{section}]")
        lines.extend(f"{key} = {_toml_value(value)}" for key, value in table.items())
        lines.append("")
    return "\n".join(lines)


def update_toml_file(path: Path, section: str, key: str, value) -> None:
    data = _read(path)
    data.setdefault(section, {})[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(data), encoding="utf-8")
