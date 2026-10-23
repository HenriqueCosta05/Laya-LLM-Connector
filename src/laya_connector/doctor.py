"""Human-readable health check of config, schemas, daemon and latency."""
from __future__ import annotations

import time

from .client import DaemonClient, DaemonError, is_loopback_url
from .config import Config
from .schemas import SchemaError, load_schemas
from .translate import build_request, parse_result

SAMPLE = "Refactor the payment service to use dependency injection and keep the tests green."


def run_checks(cfg: Config, client: DaemonClient | None = None, say=print) -> int:
    failures = 0
    client = client or DaemonClient(cfg.daemon_url, cfg.remote_key, timeout=30)

    def ok(name, detail):
        say(f"[ok] {name}: {detail}")

    def bad(name, detail):
        nonlocal failures
        failures += 1
        say(f"[!!] {name}: {detail}")

    try:
        schemas = load_schemas(cfg.schemas_dir)
        ok("schemas", ", ".join(sorted(schemas)))
    except (OSError, SchemaError, ValueError) as exc:
        bad("schemas", str(exc))
        return failures
    mode = "local (no key)" if is_loopback_url(cfg.daemon_url) else ("remote with key" if cfg.remote_key else "remote WITHOUT key")
    ok("auth", f"{cfg.daemon_url} -> {mode}")
    try:
        health = client.health()
        ok("daemon", f"device={health.get('device', '?')} loaded={','.join(health.get('loaded', [])) or '-'}")
    except DaemonError as exc:
        bad("daemon", f"{exc.kind}: {exc.detail} — start it with `uv run --script bin/laya_daemon.py start`")
        return failures
    hook = schemas["hook"]
    started = time.perf_counter()
    try:
        parse_result(hook, client.predict(build_request(hook, {hook.state_key: SAMPLE}, cfg.checkpoint)))
    except (DaemonError, KeyError, TypeError, ValueError) as exc:
        bad("latency", f"hook-shaped request failed: {exc}")
        return failures
    elapsed = time.perf_counter() - started
    detail = f"hook request {elapsed * 1000:.0f} ms (hook timeout {cfg.hook_timeout}s)"
    if elapsed > cfg.hook_timeout:
        bad("latency", detail + " — hook will fail open; trim schemas/hook.json or raise [hook] timeout")
    else:
        ok("latency", detail)
    return failures
