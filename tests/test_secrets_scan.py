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


@pytest.mark.parametrize("text", [
    "risk-management-and-compliance",
    "task-description-for-the-user",
    "disk-usage-monitoring-script",
])
def test_hyphenated_words_ending_in_sk_are_not_secrets(text):
    assert find_secrets(text) == []
    assert mask_secrets(text) == text


@pytest.mark.parametrize("prefix", ["", "key=", "'", '"', " "])
def test_openai_key_detected_after_any_boundary(prefix):
    assert find_secrets(prefix + OPENAI) == ["openai_api_key"]


PEM_BODY = "MIIEpAIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo\nJ4Zq8sQ0bZ1xYy7kLmN9oPqRsTuVwXyZ\n"
PEM_BLOCK = f"-----BEGIN RSA PRIVATE KEY-----\n{PEM_BODY}-----END RSA PRIVATE KEY-----"


def test_mask_removes_full_private_key_block_and_keeps_surrounding_text():
    masked = mask_secrets(f"before\n{PEM_BLOCK}\nafter")
    assert masked == "before\n[private_key]\nafter"
    assert "MIIEpAIBAAKCAQEA" not in masked


def test_mask_masks_unterminated_private_key_through_end_of_text():
    masked = mask_secrets(f"paste: -----BEGIN PRIVATE KEY-----\n{PEM_BODY}")
    assert masked == "paste: [private_key]"
    assert "MIIEpAIBAAKCAQEA" not in masked


def test_find_reports_private_key_for_full_and_unterminated_blocks():
    assert find_secrets(PEM_BLOCK) == ["private_key"]
    assert find_secrets(f"-----BEGIN PRIVATE KEY-----\n{PEM_BODY}") == ["private_key"]
