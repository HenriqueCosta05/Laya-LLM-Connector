import json
import os
import subprocess
import sys

from tests import answers as A
from tests.conftest import REPO


def rpc(proc, message):
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def read_response(proc, want_id):
    while True:
        line = proc.stdout.readline()
        assert line, proc.stderr.read().decode("utf-8", "replace")
        msg = json.loads(line)
        if msg.get("id") == want_id:
            return msg


def test_stdio_server_lists_and_calls_tools(fake_daemon):
    fake_daemon.responder = lambda m, p, b: (200, {"results": [A.result(commit_type=A.choice({"fix": 0.9, "feat": 0.1}))
                                                                for _ in b["states"]]})
    env = {**os.environ, "LAYA_CONNECTOR_DAEMON_URL": fake_daemon.url}
    proc = subprocess.Popen([sys.executable, str(REPO / "bin" / "laya_mcp.py")], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        init = read_response(proc, 1)
        assert "[laya]" in init["result"].get("instructions", "")
        rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in read_response(proc, 2)["result"]["tools"]}
        assert names == {"laya_classify", "laya_filter_sources", "laya_check_claim"}
        rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "laya_classify", "arguments": {"schema": "commit_type", "items": ["fix login bug"]}}})
        content = read_response(proc, 3)["result"]["content"]
        assert content[0]["text"] == "commit_type n=1 low=0\n1 fix .90"
    finally:
        proc.kill()
        proc.wait(timeout=10)
