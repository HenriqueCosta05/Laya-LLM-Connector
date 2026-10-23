"""Deterministic secret detection for prompts (runs before any model call)."""
from __future__ import annotations

import re

# Order matters: the Anthropic pattern must run before the generic OpenAI one,
# since every "sk-ant-..." key also matches "sk-...".
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_api_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
)


def find_secrets(text: str) -> list[str]:
    found: list[str] = []
    remaining = text
    for kind, pattern in PATTERNS:
        if pattern.search(remaining):
            found.append(kind)
            remaining = pattern.sub("", remaining)
    return found


def mask_secrets(text: str) -> str:
    for kind, pattern in PATTERNS:
        text = pattern.sub(f"[{kind}]", text)
    return text
