import re

import pytest

from digital_fte.payload_schema import (
    FieldError,
    FieldSpec,
    Schema,
    is_valid_payload,
    validate_payload,
)


def _task_schema(allow_unknown: bool = True) -> Schema:
    return Schema(
        {
            "task_id": FieldSpec("string", min_length=1, max_length=32),
            "title": FieldSpec("string", min_length=1),
            "priority": FieldSpec("integer", minimum=1, maximum=5),
            "tags": FieldSpec("array", required=False, max_length=3),
            "mode": FieldSpec(
                "string", required=False, choices=("fast", "thorough")
            ),
        },
        allow_unknown=allow_unknown,
    )


def _codes(errors):
    return {(e.field, e.code) for e in errors}


def test_valid_payload_passes():
    payload = {"task_id": "abc123", "title": "Do work", "priority": 3}
    assert validate_payload(payload, _task_schema()) == ()
    assert is_valid_payload(payload, _task_schema())


def test_missing_required_fields_reported():
    errors = validate_payload({"priority": 2}, _task_schema())
    assert _codes(errors) == {("task_id", "missing"), ("title", "missing")}
    assert not is_valid_payload({"priority": 2}, _task_schema())


def test_optional_field_absence_is_ok():
    payload = {"task_id": "x", "title": "t", "priority": 1}
    assert is_valid_payload(payload, _task_schema())


def test_type_mismatch_reported():
    errors = validate_payload(
        {"task_id": 5, "title": "t", "priority": "high"}, _task_schema()
    )
    assert _codes(errors) == {("task_id", "type"), ("priority", "type")}


def test_type_error_short_circuits_range_checks():
    # priority is the wrong type; only a single 'type' error, not minimum too.
    errors = validate_payload(
        {"task_id": "x", "title": "t", "priority": "9"}, _task_schema()
    )
    assert [(e.field, e.code) for e in errors] == [("priority", "type")]


def test_numeric_range_bounds():
    below = validate_payload(
        {"task_id": "x", "title": "t", "priority": 0}, _task_schema()
    )
    above = validate_payload(
        {"task_id": "x", "title": "t", "priority": 6}, _task_schema()
    )
    assert _codes(below) == {("priority", "minimum")}
    assert _codes(above) == {("priority", "maximum")}


def test_boolean_rejected_for_numeric_field():
    # True is an int in Python; the validator must not accept it as a number.
    errors = validate_payload(
        {"task_id": "x", "title": "t", "priority": True}, _task_schema()
    )
    assert _codes(errors) == {("priority", "type")}


def test_string_length_bounds():
    errors = validate_payload(
        {"task_id": "", "title": "t", "priority": 1}, _task_schema()
    )
    assert _codes(errors) == {("task_id", "min_length")}
    errors = validate_payload(
        {"task_id": "y" * 40, "title": "t", "priority": 1}, _task_schema()
    )
    assert _codes(errors) == {("task_id", "max_length")}


def test_array_length_bound():
    errors = validate_payload(
        {"task_id": "x", "title": "t", "priority": 1, "tags": [1, 2, 3, 4]},
        _task_schema(),
    )
    assert _codes(errors) == {("tags", "max_length")}


def test_tuple_accepted_as_array():
    payload = {"task_id": "x", "title": "t", "priority": 1, "tags": ("a",)}
    assert is_valid_payload(payload, _task_schema())


def test_choices_enforced():
    errors = validate_payload(
        {"task_id": "x", "title": "t", "priority": 1, "mode": "turbo"},
        _task_schema(),
    )
    assert _codes(errors) == {("mode", "choice")}


def test_pattern_matching():
    schema = Schema({"code": FieldSpec("string", pattern=r"[A-Z]{3}-\d+")})
    assert is_valid_payload({"code": "ABC-42"}, schema)
    errors = validate_payload({"code": "abc-42"}, schema)
    assert _codes(errors) == {("code", "pattern")}
    # Pattern must match the whole string, not a prefix.
    assert not is_valid_payload({"code": "ABC-42x"}, schema)


def test_unknown_fields_allowed_by_default():
    payload = {"task_id": "x", "title": "t", "priority": 1, "extra": 9}
    assert is_valid_payload(payload, _task_schema(allow_unknown=True))


def test_unknown_fields_rejected_when_disabled():
    payload = {"task_id": "x", "title": "t", "priority": 1, "zzz": 1, "aaa": 2}
    errors = validate_payload(payload, _task_schema(allow_unknown=False))
    assert _codes(errors) == {("aaa", "unknown_field"), ("zzz", "unknown_field")}
    # Unknown keys reported in sorted order for determinism.
    unknown = [e.field for e in errors if e.code == "unknown_field"]
    assert unknown == ["aaa", "zzz"]


def test_non_dict_payload_reported():
    errors = validate_payload(["not", "a", "dict"], _task_schema())
    assert [(e.field, e.code) for e in errors] == [("", "not_an_object")]


def test_errors_follow_declaration_order():
    errors = validate_payload({}, _task_schema())
    fields = [e.field for e in errors]
    assert fields == ["task_id", "title", "priority"]


def test_multiple_errors_collected_at_once():
    errors = validate_payload(
        {"task_id": "", "priority": 99, "mode": "nope"}, _task_schema()
    )
    assert _codes(errors) == {
        ("task_id", "min_length"),
        ("title", "missing"),
        ("priority", "maximum"),
        ("mode", "choice"),
    }


def test_number_type_accepts_int_and_float():
    schema = Schema({"ratio": FieldSpec("number", minimum=0, maximum=1)})
    assert is_valid_payload({"ratio": 0.5}, schema)
    assert is_valid_payload({"ratio": 1}, schema)
    assert not is_valid_payload({"ratio": 1.5}, schema)


def test_integer_field_rejects_float():
    schema = Schema({"n": FieldSpec("integer")})
    assert _codes(validate_payload({"n": 1.0}, schema)) == {("n", "type")}


def test_fielderror_is_frozen_dataclass():
    err = FieldError("f", "missing", "gone")
    with pytest.raises(AttributeError):
        err.code = "x"  # type: ignore[misc]


def test_fieldspec_rejects_unknown_type():
    with pytest.raises(ValueError):
        FieldSpec("timestamp")


def test_fieldspec_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        FieldSpec("integer", minimum=10, maximum=1)
    with pytest.raises(ValueError):
        FieldSpec("string", min_length=5, max_length=2)


def test_fieldspec_rejects_bad_pattern():
    with pytest.raises(re.error):
        FieldSpec("string", pattern="[unclosed")


def test_schema_requires_fields():
    with pytest.raises(ValueError):
        Schema({})


def test_schema_rejects_non_spec_values():
    with pytest.raises(TypeError):
        Schema({"x": "string"})  # type: ignore[dict-item]
