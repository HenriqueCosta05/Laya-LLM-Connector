"""laya.serve.create_app() behind origin-based auth: local passes, remote needs a bearer."""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import socket
import struct
from pathlib import Path

from . import config


def is_wsl(proc_version: str) -> bool:
    return "microsoft" in proc_version.lower()


def parse_default_gateway(route_table: str) -> str | None:
    for line in route_table.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "00000000":
            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    return None


def detect_wsl_gateway() -> str | None:
    try:
        if not is_wsl(Path("/proc/version").read_text(encoding="utf-8")):
            return None
        return parse_default_gateway(Path("/proc/net/route").read_text(encoding="utf-8"))
    except OSError:
        return None


WSL_NAT = ipaddress.ip_network("172.16.0.0/12")


def _trustable_gateway(gateway: str | None) -> bool:
    try:
        return gateway is not None and ipaddress.ip_address(gateway) in WSL_NAT
    except ValueError:
        return False


def trusted_networks(extra: tuple[str, ...], wsl_gateway: str | None, trust_wsl_gateway: bool = True):
    nets = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")]
    if trust_wsl_gateway and _trustable_gateway(wsl_gateway):
        nets.append(ipaddress.ip_network(f"{wsl_gateway}/32"))
    nets.extend(ipaddress.ip_network(cidr, strict=False) for cidr in extra)
    return nets


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class UnsafeBindError(RuntimeError):
    pass


def check_bind(host: str, remote_key: str | None) -> None:
    if not is_loopback_host(host) and not remote_key:
        raise UnsafeBindError(f"refusing to bind {host} without remote_key; run bin/laya_setup.py "
                              "or set daemon.host = \"127.0.0.1\"")


async def _send_json(send, status: int, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
    await send({"type": "http.response.body", "body": data})


class OriginAuth:
    def __init__(self, app, trusted, remote_key: str | None):
        self.app = app
        self.trusted = list(trusted)
        self.expected = f"Bearer {remote_key}".encode("utf-8") if remote_key else None

    def _is_trusted(self, ip) -> bool:
        try:
            address = ipaddress.ip_address(ip)
        except (TypeError, ValueError):
            return False
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        return any(address in net for net in self.trusted if net.version == address.version)

    def _authorized(self, scope) -> bool:
        if self.expected is None:
            return False
        supplied = dict(scope.get("headers") or []).get(b"authorization", b"")
        return hmac.compare_digest(supplied, self.expected)

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        client = scope.get("client")
        if self._is_trusted(client[0] if client else None) or self._authorized(scope):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope.get("path") == "/health":
            return await _send_json(send, 200, {"status": "ok"})
        return await _send_json(send, 401, {"detail": "invalid or missing bearer token"})


def laya_env(cfg: config.Config) -> dict[str, str]:
    env = {"LAYA_MODELS": cfg.checkpoint, "LAYA_MAX_LOADED": "1", "LAYA_PRELOAD": "1"}
    if cfg.device:
        env["LAYA_DEVICE"] = cfg.device
    return env


def main(root: Path) -> None:
    cfg = config.load(root)
    check_bind(cfg.host, cfg.remote_key)
    os.environ.pop("LAYA_API_KEY", None)
    os.environ.pop("LAYA_DEVICE", None)
    os.environ.update(laya_env(cfg))

    import uvicorn
    from laya.serve import create_app

    app = OriginAuth(create_app(), trusted_networks(cfg.trusted_local, detect_wsl_gateway(), cfg.trust_wsl_gateway), cfg.remote_key)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info", proxy_headers=False)


if __name__ == "__main__":
    main(Path(os.environ.get("LAYA_CONNECTOR_ROOT", ".")).resolve())
