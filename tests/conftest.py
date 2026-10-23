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


class FakeDaemon:
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
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

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
