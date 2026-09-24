import pytest

from digital_fte.config_validator import (
    ConfigValidationError,
    FieldSpec,
    ValidationResult,
    check_config,
    validate_config,
)


def _schema():
    return {
        "workers": FieldSpec(type=int, min=1, max=64),
        "name": FieldSpec(type=str),
        "ratio": FieldSpec(type=float, min=0.0, max=1.0, required=False, default=0.5),
        "mode": FieldSpec(type=str, choices=("fast", "safe"), required=False, default="safe"),
    }


def test_valid_config_passes():
    result = check_config({"workers": 4, "name": "job"}, _schema())
    assert result.ok is True
    assert result.values["workers"] == 4
    assert result.values["name"] == "job"


def test_defaults_applied_for_optional_keys():
    result = check_config({"workers": 4, "name": "job"}, _schema())
    assert result.values["ratio"] == 0.5
    assert result.values["mode"] == "safe"


def test_missing_required_key_reported():
    result = check_config({"workers": 4}, _schema())
    assert result.ok is False
    assert any("name" in e for e in result.errors)


def test_wrong_type_reported():
    result = check_config({"workers": "four", "name": "job"}, _schema())
    assert result.ok is False
    assert any("workers" in e for e in result.errors)


def test_bool_rejected_for_int_field():
    result = check_config({"workers": True, "name": "job"}, _schema())
    assert result.ok is False
    assert any("bool" in e for e in result.errors)


def test_min_bound_enforced():
    result = check_config({"workers": 0, "name": "job"}, _schema())
    assert result.ok is False
    assert any(">=" in e for e in result.errors)


def test_max_bound_enforced():
    result = check_config({"workers": 100, "name": "job"}, _schema())
    assert result.ok is False
    assert any("<=" in e for e in result.errors)


def test_choices_enforced():
    result = check_config(
        {"workers": 4, "name": "job", "mode": "turbo"}, _schema()
    )
    assert result.ok is False
    assert any("mode" in e for e in result.errors)


def test_all_errors_collected():
    result = check_config({"workers": 0}, _schema())
    # both missing name and out-of-range workers
    assert len(result.errors) >= 2


def test_validate_config_raises_with_errors():
    with pytest.raises(ConfigValidationError) as exc:
        validate_config({"workers": 0}, _schema())
    assert len(exc.value.errors) >= 1


def test_validate_config_returns_normalised_values():
    values = validate_config({"workers": 4, "name": "job"}, _schema())
    assert values == {"workers": 4, "name": "job", "ratio": 0.5, "mode": "safe"}


def test_field_spec_type_must_be_a_type():
    with pytest.raises(TypeError):
        FieldSpec(type=123)  # type: ignore[arg-type]


def test_non_mapping_config_rejected():
    with pytest.raises(TypeError):
        check_config(["not", "a", "map"], _schema())  # type: ignore[arg-type]


def test_schema_value_must_be_field_spec():
    with pytest.raises(TypeError):
        check_config({"x": 1}, {"x": "nope"})  # type: ignore[dict-item]


def test_result_type():
    result = check_config({"workers": 4, "name": "job"}, _schema())
    assert isinstance(result, ValidationResult)
