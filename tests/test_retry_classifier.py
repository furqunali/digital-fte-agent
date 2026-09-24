import pytest

from digital_fte.retry_classifier import (
    PERMANENT,
    TRANSIENT,
    UNKNOWN,
    Classification,
    classify,
    is_transient,
)


def test_timeout_type_is_transient():
    result = classify(TimeoutError("boom"))
    assert result.disposition == TRANSIENT
    assert result.is_transient is True


def test_connection_error_is_transient():
    assert classify(ConnectionResetError()).disposition == TRANSIENT


def test_value_error_is_permanent():
    result = classify(ValueError("bad input"))
    assert result.disposition == PERMANENT
    assert result.is_permanent is True


def test_permission_error_is_permanent():
    assert classify(PermissionError()).disposition == PERMANENT


def test_classify_by_type_name_string():
    assert classify("ConnectionTimeout").disposition == TRANSIENT
    assert classify("KeyError").disposition == PERMANENT


def test_classify_by_exception_class():
    assert classify(TimeoutError).disposition == TRANSIENT
    assert classify(TypeError).disposition == PERMANENT


def test_message_signal_transient():
    result = classify("SomeVendorError", "the service is temporarily unavailable")
    assert result.disposition == TRANSIENT


def test_message_signal_permanent():
    result = classify("SomeVendorError", "resource not found")
    assert result.disposition == PERMANENT


def test_http_429_in_message_transient():
    assert classify("HTTPError", "got 429 from upstream").disposition == TRANSIENT


def test_http_404_in_message_permanent():
    assert classify("HTTPError", "server returned 404").disposition == PERMANENT


def test_unknown_when_no_signal():
    result = classify("MysteryError", "something happened")
    assert result.disposition == UNKNOWN
    assert result.is_transient is False
    assert result.is_permanent is False


def test_type_signal_beats_message_signal():
    # Transient type name, but message mentions a permanent keyword.
    result = classify("ConnectionError", "invalid state")
    assert result.disposition == TRANSIENT


def test_instance_message_used_when_message_omitted():
    result = classify(RuntimeError("connection refused"))
    assert result.disposition == TRANSIENT


def test_message_override_wins_over_instance_text():
    # Instance text alone would be unknown; override supplies a transient hint.
    result = classify(RuntimeError("weird"), "timed out")
    assert result.disposition == TRANSIENT


def test_is_transient_helper():
    assert is_transient(TimeoutError()) is True
    assert is_transient(ValueError()) is False


def test_reason_is_populated():
    assert "type name" in classify(TimeoutError()).reason


def test_bad_error_type_rejected():
    with pytest.raises(TypeError):
        classify(123)


def test_bad_message_type_rejected():
    with pytest.raises(TypeError):
        classify("SomeError", message=123)


def test_classification_is_frozen():
    from dataclasses import FrozenInstanceError

    c = Classification(TRANSIENT, "x")
    with pytest.raises(FrozenInstanceError):
        c.disposition = PERMANENT  # type: ignore[misc]
