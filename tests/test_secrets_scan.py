import pytest

from laya_connector.secrets_scan import find_secrets, mask_secrets

ANTHROPIC = "sk-ant-api03-" + "A" * 40
OPENAI = "sk-proj-" + "b" * 40
GITHUB = "ghp_" + "c" * 36
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"


@pytest.mark.parametrize("text,kind", [
    (f"use {ANTHROPIC} please", "anthropic_api_key"),
    (f"key={OPENAI}", "openai_api_key"),
    (f"token {GITHUB}", "github_token"),
    (f"aws {AWS} here", "aws_access_key"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nabc", "private_key"),
    (f"bearer {JWT}", "jwt"),
    ("xoxb-1234567890-abcdef", "slack_token"),
])
def test_detects_each_kind(text, kind):
    assert find_secrets(text) == [kind]


def test_anthropic_key_is_not_double_counted_as_openai():
    assert find_secrets(ANTHROPIC) == ["anthropic_api_key"]


@pytest.mark.parametrize("text", [
    "refactor the payment service",
    "the variable sk-short is fine",
    "explain AKIA prefix conventions",
    "",
])
def test_ignores_benign_text(text):
    assert find_secrets(text) == []


def test_mask_replaces_values_with_kind():
    masked = mask_secrets(f"a {ANTHROPIC} b {GITHUB}")
    assert ANTHROPIC not in masked and GITHUB not in masked
    assert masked == "a [anthropic_api_key] b [github_token]"
