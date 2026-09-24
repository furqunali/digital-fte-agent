import pytest

from digital_fte.env_schema import (
    MISSING,
    EnvParseError,
    EnvVar,
    parse_env,
)


def test_parses_all_types():
    spec = {
        "COUNT": EnvVar(type="int"),
        "RATIO": EnvVar(type="float"),
        "FLAG": EnvVar(type="bool"),
        "NAME": EnvVar(type="str"),
    }
    env = {"COUNT": "5", "RATIO": "0.25", "FLAG": "true", "NAME": "job"}
    result = parse_env(env, spec)
    assert result == {"COUNT": 5, "RATIO": 0.25, "FLAG": True, "NAME": "job"}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("0", False), ("no", False), ("off", False),
    ],
)
def test_bool_spellings(raw, expected):
    result = parse_env({"F": raw}, {"F": EnvVar(type="bool")})
    assert result["F"] is expected


def test_invalid_bool_rejected():
    with pytest.raises(EnvParseError):
        parse_env({"F": "maybe"}, {"F": EnvVar(type="bool")})


def test_invalid_int_rejected():
    with pytest.raises(EnvParseError):
        parse_env({"C": "3.5"}, {"C": EnvVar(type="int")})


def test_invalid_float_rejected():
    with pytest.raises(EnvParseError):
        parse_env({"R": "abc"}, {"R": EnvVar(type="float")})


def test_non_finite_float_rejected():
    with pytest.raises(EnvParseError):
        parse_env({"R": "inf"}, {"R": EnvVar(type="float")})


def test_default_used_when_absent():
    spec = {"C": EnvVar(type="int", default=7)}
    assert parse_env({}, spec) == {"C": 7}


def test_absent_without_default_is_omitted():
    spec = {"C": EnvVar(type="int")}
    assert parse_env({}, spec) == {}


def test_required_missing_raises():
    spec = {"C": EnvVar(type="int", required=True)}
    with pytest.raises(EnvParseError):
        parse_env({}, spec)


def test_required_with_default_still_required():
    spec = {"C": EnvVar(type="int", default=7, required=True)}
    with pytest.raises(EnvParseError):
        parse_env({}, spec)


def test_whitespace_trimmed_for_numbers():
    assert parse_env({"C": "  5  "}, {"C": EnvVar(type="int")})["C"] == 5


def test_str_type_preserves_raw():
    assert parse_env({"N": "  spaced  "}, {"N": EnvVar(type="str")})["N"] == "  spaced  "


def test_bad_env_var_type_rejected():
    with pytest.raises(ValueError):
        EnvVar(type="decimal")


def test_non_string_raw_rejected():
    with pytest.raises(TypeError):
        parse_env({"C": 5}, {"C": EnvVar(type="int")})  # type: ignore[dict-item]


def test_spec_value_must_be_envvar():
    with pytest.raises(TypeError):
        parse_env({"C": "5"}, {"C": "int"})  # type: ignore[dict-item]


def test_missing_sentinel_is_singleton():
    assert MISSING is MISSING
    assert EnvVar(type="int").default is MISSING
