import pytest

from digital_fte.idempotency_key import idempotency_key, matches


def test_returns_64_char_hex():
    key = idempotency_key({"a": 1})
    assert isinstance(key, str)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_deterministic_for_same_payload():
    payload = {"user": "abc", "amount": 10}
    assert idempotency_key(payload) == idempotency_key(dict(payload))


def test_key_order_does_not_matter():
    a = idempotency_key({"x": 1, "y": 2})
    b = idempotency_key({"y": 2, "x": 1})
    assert a == b


def test_nested_key_order_does_not_matter():
    a = idempotency_key({"outer": {"a": 1, "b": 2}})
    b = idempotency_key({"outer": {"b": 2, "a": 1}})
    assert a == b


def test_value_change_changes_key():
    assert idempotency_key({"a": 1}) != idempotency_key({"a": 2})


def test_list_order_is_significant():
    assert idempotency_key({"items": [1, 2]}) != idempotency_key({"items": [2, 1]})


def test_namespace_changes_key():
    base = idempotency_key({"a": 1})
    ns = idempotency_key({"a": 1}, namespace="tenant-1")
    assert base != ns


def test_namespace_is_unambiguous():
    # A prefix-collision style attempt must not produce the same key.
    a = idempotency_key({"a": 1}, namespace="ab")
    b = idempotency_key({"a": 1}, namespace="a")
    assert a != b


def test_non_dict_payload_rejected():
    with pytest.raises(TypeError):
        idempotency_key(["not", "a", "dict"])


def test_non_string_key_rejected():
    with pytest.raises(TypeError):
        idempotency_key({1: "one"})


def test_non_finite_float_rejected():
    with pytest.raises(ValueError):
        idempotency_key({"x": float("nan")})
    with pytest.raises(ValueError):
        idempotency_key({"x": float("inf")})


def test_unsupported_value_rejected():
    with pytest.raises(TypeError):
        idempotency_key({"x": object()})


def test_non_string_namespace_rejected():
    with pytest.raises(TypeError):
        idempotency_key({"a": 1}, namespace=5)


def test_matches_true_and_false():
    payload = {"a": 1, "b": [1, 2]}
    key = idempotency_key(payload)
    assert matches(payload, key) is True
    assert matches({"a": 2}, key) is False


def test_matches_rejects_non_string_key():
    with pytest.raises(TypeError):
        matches({"a": 1}, 123)
