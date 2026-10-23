import pytest

from laya_connector.client import DaemonClient, DaemonError, is_loopback_url


@pytest.mark.parametrize("url,expected", [
    ("http://127.0.0.1:8000", True), ("http://localhost:8000", True), ("http://[::1]:8000", True),
    ("http://192.168.1.5:8000", False), ("http://laya.example.com", False),
])
def test_is_loopback_url(url, expected):
    assert is_loopback_url(url) is expected


def test_predict_posts_json(fake_daemon):
    fake_daemon.responder = lambda m, p, b: (200, {"answers": {}, "echo": b})
    out = DaemonClient(fake_daemon.url).predict({"state": "x", "questions": {}})
    assert out["echo"] == {"state": "x", "questions": {}}
    method, path, headers, _ = fake_daemon.requests[0]
    assert (method, path) == ("POST", "/v1/systemone") and "authorization" not in headers


def test_batch_and_health_paths(fake_daemon):
    client = DaemonClient(fake_daemon.url)
    client.predict_batch({"states": []})
    client.health()
    assert [(r[0], r[1]) for r in fake_daemon.requests] == [("POST", "/v1/systemone/batch"), ("GET", "/health")]


def test_key_not_sent_to_loopback_even_if_configured(fake_daemon):
    DaemonClient(fake_daemon.url, remote_key="secret").health()
    assert "authorization" not in fake_daemon.requests[0][2]


def test_key_sent_to_non_loopback(monkeypatch):
    client = DaemonClient("http://10.1.2.3:8000", remote_key="secret")
    assert client._headers()["authorization"] == "Bearer secret"


def test_401_is_auth_error(fake_daemon):
    fake_daemon.responder = lambda m, p, b: (401, {"detail": "no"})
    with pytest.raises(DaemonError) as err:
        DaemonClient(fake_daemon.url).health()
    assert err.value.kind == "auth"


def test_500_is_http_error(fake_daemon):
    fake_daemon.responder = lambda m, p, b: (500, {"detail": "boom"})
    with pytest.raises(DaemonError) as err:
        DaemonClient(fake_daemon.url).predict({})
    assert err.value.kind == "http" and "500" in err.value.detail


def test_timeout(fake_daemon):
    fake_daemon.delay = 1.0
    with pytest.raises(DaemonError) as err:
        DaemonClient(fake_daemon.url, timeout=0.2).health()
    assert err.value.kind == "timeout"


def test_connection_refused():
    with pytest.raises(DaemonError) as err:
        DaemonClient("http://127.0.0.1:9", timeout=1).health()
    assert err.value.kind in ("unavailable", "timeout")
