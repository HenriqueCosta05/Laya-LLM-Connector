"""UserPromptSubmit: filter, scan, one Laya call, one compact line."""
from __future__ import annotations

import time

from .client import DaemonClient, DaemonError
from .config import Config
from .format import hook_line
from .log import JsonlLogger
from .paths import truncate
from .policy import guard_warnings, suggest_tier, user_message
from .schemas import Schema
from .secrets_scan import find_secrets
from .translate import build_request, parse_result


def handle(event: dict, cfg: Config, client: DaemonClient, schema: Schema, logger: JsonlLogger) -> dict | None:
    prompt = str(event.get("prompt") or "")
    base = {"session_id": event.get("session_id"), "prompt": prompt, "schema": f"{schema.name}@{schema.version}"}
    stripped = prompt.strip()
    if stripped.startswith("/") or len(stripped) < cfg.hook_min_chars:
        logger.write({**base, "action": "skip"})
        return None

    found = find_secrets(prompt)
    if found:
        logger.write({**base, "action": "block", "secrets": found})
        return {"decision": "block", "reason": f"segredo detectado ({', '.join(found)}); remova e reenvie"}

    started = time.perf_counter()
    state = {schema.state_key: truncate(prompt, cfg.hook_max_chars)}
    try:
        result = client.predict(build_request(schema, state, cfg.checkpoint), timeout=cfg.hook_timeout)
        decisions = parse_result(schema, result)
    except (DaemonError, KeyError, TypeError, ValueError, AttributeError) as exc:
        logger.write({**base, "action": "fail_open", "error": str(exc),
                      "latency_ms": round((time.perf_counter() - started) * 1000)})
        return None
    latency_ms = round((time.perf_counter() - started) * 1000)

    tier = suggest_tier(decisions)
    warnings = guard_warnings(decisions)
    line = hook_line(decisions)
    message = user_message(tier, warnings)

    output: dict = {}
    if line:
        output["hookSpecificOutput"] = {"hookEventName": "UserPromptSubmit", "additionalContext": line}
    if message:
        output["systemMessage"] = message
    action = "warn" if warnings else ("inject" if line else "skip")
    logger.write({
        **base, "action": action, "latency_ms": latency_ms, "tier": tier.name if tier else None,
        "decisions": {qid: {"label": d.label, "value": round(d.value, 4), "confidence": round(d.confidence, 4),
                            "low": d.low} for qid, d in decisions.items()},
        "probabilities": {qid: result["answers"][qid].get("probabilities", {"true": result["answers"][qid].get("noul")})
                          for qid in decisions},
    })
    return output or None
