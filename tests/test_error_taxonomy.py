import pytest

from digital_fte.error_taxonomy import (
    AUTH,
    CATEGORIES,
    NETWORK,
    RATE_LIMIT,
    UNKNOWN,
    VALIDATION,
    CategorizedError,
    categorize,
    category_of,
)


def test_network_from_timeout():
    assert categorize(TimeoutError("timed out")).category == NETWORK


def test_network_from_connection():
    assert categorize(ConnectionResetError("connection reset")).category == NETWORK


def test_auth_from_message():
    assert categorize("HTTPError", "401 unauthorized").category == AUTH


def test_auth_from_forbidden():
    assert categorize("HTTPError", "403 forbidden").category == AUTH


def test_rate_limit_from_429():
    assert categorize("HTTPError", "429 too many requests").category == RATE_LIMIT


def test_rate_limit_beats_auth_precedence():
    # message has both throttle and a generic hint; rate_limit rule runs first
    assert categorize("Error", "rate limit exceeded").category == RATE_LIMIT


def test_validation_from_valueerror():
    assert categorize(ValueError("bad")).category == VALIDATION


def test_validation_from_message():
    assert categorize("SchemaError", "missing field 'name'").category == VALIDATION


def test_unknown_when_nothing_matches():
    assert categorize("MysteryError", "just weird").category == UNKNOWN


def test_category_of_helper():
    assert category_of(TimeoutError()) == NETWORK


def test_accepts_exception_class():
    assert categorize(ConnectionError).category == NETWORK


def test_accepts_type_name_string():
    assert categorize("ConnectionRefusedError").category == NETWORK


def test_instance_message_used():
    assert categorize(RuntimeError("service unavailable 503")).category == NETWORK


def test_message_override():
    assert categorize(RuntimeError("weird"), "quota exceeded").category == RATE_LIMIT


def test_all_categories_are_known():
    assert set(CATEGORIES) == {NETWORK, AUTH, RATE_LIMIT, VALIDATION, UNKNOWN}


def test_reason_is_populated():
    result = categorize(TimeoutError())
    assert isinstance(result, CategorizedError)
    assert result.reason


def test_bad_error_type_rejected():
    with pytest.raises(TypeError):
        categorize(3.14)


def test_bad_message_type_rejected():
    with pytest.raises(TypeError):
        categorize("Error", message=[])


def test_categorized_error_is_frozen():
    from dataclasses import FrozenInstanceError

    c = CategorizedError(NETWORK, "x")
    with pytest.raises(FrozenInstanceError):
        c.category = AUTH  # type: ignore[misc]
