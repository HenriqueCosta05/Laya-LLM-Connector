from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from laya_connector.config import Config
from laya_connector.schemas import load_schemas

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def make_cfg(tmp_path):
    def _make(**overrides) -> Config:
        return Config(root=tmp_path, **overrides)
    return _make


@pytest.fixture
def cfg(make_cfg) -> Config:
    return make_cfg()


@pytest.fixture(scope="session")
def schemas():
    return load_schemas(REPO / "schemas")


DROP = object()


class Truncated:
    """Response body whose content-length declares more bytes than are sent."""

    def __init__(self, body: bytes, declared: int):
        self.body = body
        self.declared = declared


class FakeDaemon:
    """Responder may return (status, dict) as before, (status, bytes) for a raw body,
    (status, Truncated(...)) for a short body, or DROP to close without a response."""

    DROP = DROP
    Truncated = Truncated

    def __init__(self):
        self.requests = []
        self.responder = lambda method, path, body: (200, {"status": "ok"})
        self.delay = 0.0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self, method):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else None
                fake.requests.append((method, self.path, {k.lower(): v for k, v in self.headers.items()}, body))
                if fake.delay:
                    time.sleep(fake.delay)
                status, payload = fake.responder(method, self.path, body)
                if payload is DROP:
                    self.close_connection = True
                    return
                truncated = isinstance(payload, Truncated)
                if truncated:
                    data, declared = payload.body, payload.declared
                elif isinstance(payload, bytes):
                    data = payload
                    declared = len(payload)
                else:
                    data = json.dumps(payload).encode("utf-8")
                    declared = len(data)
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(declared))
                if 300 <= status < 400:
                    self.send_header("location", fake.url + "/elsewhere")
                self.end_headers()
                self.wfile.write(data)
                if truncated:
                    self.close_connection = True

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_daemon():
    daemon = FakeDaemon()
    yield daemon
    daemon.close()
