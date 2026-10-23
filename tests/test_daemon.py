import asyncio
import json

import pytest

from laya_connector import daemon

ROUTE = ("Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\n"
         "eth0\t00000000\t0100A8C0\t0003\t0\t0\t0\t00000000\n"
         "eth0\t0000A8C0\t00000000\t0001\t0\t0\t0\t00FFFFFF\n")


def test_is_wsl():
    assert daemon.is_wsl("Linux version 5.15.0-microsoft-standard-WSL2")
    assert not daemon.is_wsl("Linux version 6.8.0-generic")


def test_parse_default_gateway():
    assert daemon.parse_default_gateway(ROUTE) == "192.168.0.1"
    assert daemon.parse_default_gateway("Iface\tDestination\n") is None


def test_check_bind():
    daemon.check_bind("127.0.0.1", None)
    daemon.check_bind("0.0.0.0", "k")
    with pytest.raises(daemon.UnsafeBindError):
        daemon.check_bind("0.0.0.0", None)


def test_laya_env(make_cfg):
    env = daemon.laya_env(make_cfg(device="cuda", checkpoint="multilingual"))
    assert env == {"LAYA_MODELS": "multilingual", "LAYA_MAX_LOADED": "1", "LAYA_PRELOAD": "1", "LAYA_DEVICE": "cuda"}
    assert "LAYA_DEVICE" not in daemon.laya_env(make_cfg(device=""))


def call(middleware, ip, path="/v1/systemone", auth=None):
    seen = {}

    async def app(scope, receive, send):
        seen["called"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"inner"})

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    headers = [(b"authorization", auth.encode())] if auth else []
    scope = {"type": "http", "path": path, "client": (ip, 5555), "headers": headers}
    asyncio.run(middleware(app)(scope, receive, send))
    status = sent[0]["status"]
    body = b"".join(m.get("body", b"") for m in sent[1:])
    return status, body, seen.get("called", False)


def make(remote_key="k", gateway="172.20.0.1", extra=()):
    nets = daemon.trusted_networks(extra, gateway)
    return lambda app: daemon.OriginAuth(app, nets, remote_key)


@pytest.mark.parametrize("ip", ["127.0.0.1", "127.8.9.10", "::1", "::ffff:127.0.0.1", "172.20.0.1"])
def test_local_passes_without_key(ip):
    assert call(make(), ip)[2] is True


def test_extra_trusted_cidr():
    assert call(make(extra=("10.0.0.0/8",)), "10.1.2.3")[2] is True


def test_remote_requires_key():
    assert call(make(), "203.0.113.5")[:2] == (401, json.dumps({"detail": "invalid or missing bearer token"}).encode())
    assert call(make(), "203.0.113.5", auth="Bearer wrong")[0] == 401
    assert call(make(), "203.0.113.5", auth="Bearer k")[2] is True


def test_remote_without_configured_key_is_refused():
    assert call(make(remote_key=None), "203.0.113.5", auth="Bearer ")[0] == 401


def test_remote_health_is_status_only():
    status, body, called = call(make(), "203.0.113.5", path="/health")
    assert (status, json.loads(body), called) == (200, {"status": "ok"}, False)
