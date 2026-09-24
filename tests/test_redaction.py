import pytest

from digital_fte.redaction import (
    API_KEY_PLACEHOLDER,
    EMAIL_PLACEHOLDER,
    GENERIC_PLACEHOLDER,
    contains_secret,
    redact,
    redact_verbose,
)


def test_email_is_masked():
    out = redact("contact furqan@zakoil.com now")
    assert "furqan@zakoil.com" not in out
    assert EMAIL_PLACEHOLDER in out


def test_multiple_emails_masked():
    result = redact_verbose("a@b.com and c@d.org")
    assert result.counts["email"] == 2
    assert "@" not in result.text.replace(EMAIL_PLACEHOLDER, "")


def test_bearer_token_masked():
    out = redact("Authorization: Bearer abc.def-123XYZ")
    assert "abc.def-123XYZ" not in out
    assert "Bearer [REDACTED_TOKEN]" in out


def test_provider_key_masked():
    out = redact("using key sk-ABCDEFGH12345678 today")
    assert "sk-ABCDEFGH12345678" not in out
    assert API_KEY_PLACEHOLDER in out


def test_aws_style_key_masked():
    out = redact("AKIAIOSFODNN7EXAMPLE leaked")
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert API_KEY_PLACEHOLDER in out


def test_assigned_secret_keeps_label():
    out = redact("password=hunter2")
    assert "hunter2" not in out
    assert "password=" in out
    assert GENERIC_PLACEHOLDER in out


def test_assigned_api_key_masked():
    out = redact('api_key="topsecretvalue"')
    assert "topsecretvalue" not in out
    assert "api_key=" in out


def test_clean_text_unchanged():
    text = "nothing sensitive here, just a normal log line"
    assert redact(text) == text


def test_contains_secret_true_and_false():
    assert contains_secret("email me at x@y.com") is True
    assert contains_secret("plain text") is False


def test_counts_reported_per_category():
    result = redact_verbose("x@y.com and token=abc123 and Bearer zzz")
    assert result.counts.get("email") == 1
    assert result.counts.get("assigned_secret") == 1
    assert result.counts.get("bearer") == 1


def test_deterministic():
    text = "email a@b.com token=secret"
    assert redact(text) == redact(text)


def test_verbose_empty_counts_when_clean():
    result = redact_verbose("clean line")
    assert result.counts == {}
    assert result.text == "clean line"


def test_non_string_rejected():
    with pytest.raises(TypeError):
        redact(12345)


def test_verbose_non_string_rejected():
    with pytest.raises(TypeError):
        redact_verbose(None)


def test_multiple_secret_types_in_one_line():
    out = redact("user a@b.com used sk-ABCDEFGH1234 and password=pw")
    assert "a@b.com" not in out
    assert "sk-ABCDEFGH1234" not in out
    assert "pw" not in out.split("password=")[1][:10]
