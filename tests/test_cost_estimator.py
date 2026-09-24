from dataclasses import FrozenInstanceError

import pytest

from digital_fte.cost_estimator import CostBreakdown, estimate_cost


# --- core -------------------------------------------------------------------

def test_basic_estimate():
    result = estimate_cost(
        1000, 500, prompt_rate_per_1k=0.01, completion_rate_per_1k=0.03
    )
    assert result.prompt_cost == pytest.approx(0.01)
    assert result.completion_cost == pytest.approx(0.015)
    assert result.total_cost == pytest.approx(0.025)


def test_total_tokens():
    result = estimate_cost(
        1200, 800, prompt_rate_per_1k=0.0, completion_rate_per_1k=0.0
    )
    assert result.total_tokens == 2000


def test_zero_tokens_zero_cost():
    result = estimate_cost(
        0, 0, prompt_rate_per_1k=0.01, completion_rate_per_1k=0.03
    )
    assert result.total_cost == 0.0


def test_fractional_thousands():
    result = estimate_cost(
        500, 0, prompt_rate_per_1k=0.02, completion_rate_per_1k=0.04
    )
    assert result.prompt_cost == pytest.approx(0.01)


def test_deterministic():
    a = estimate_cost(1234, 567, prompt_rate_per_1k=0.5, completion_rate_per_1k=1.5)
    b = estimate_cost(1234, 567, prompt_rate_per_1k=0.5, completion_rate_per_1k=1.5)
    assert a == b


# --- record shape -----------------------------------------------------------

def test_returns_breakdown():
    result = estimate_cost(10, 20, prompt_rate_per_1k=1.0, completion_rate_per_1k=2.0)
    assert isinstance(result, CostBreakdown)
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20


def test_is_frozen():
    result = estimate_cost(10, 20, prompt_rate_per_1k=1.0, completion_rate_per_1k=2.0)
    with pytest.raises(FrozenInstanceError):
        result.total_cost = 0.0  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        estimate_cost(-1, 0, prompt_rate_per_1k=1.0, completion_rate_per_1k=1.0)


def test_float_tokens_rejected():
    with pytest.raises(TypeError):
        estimate_cost(1.5, 0, prompt_rate_per_1k=1.0, completion_rate_per_1k=1.0)


def test_bool_tokens_rejected():
    with pytest.raises(TypeError):
        estimate_cost(True, 0, prompt_rate_per_1k=1.0, completion_rate_per_1k=1.0)


def test_negative_rate_rejected():
    with pytest.raises(ValueError):
        estimate_cost(10, 10, prompt_rate_per_1k=-0.1, completion_rate_per_1k=1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_rate_rejected(bad):
    with pytest.raises(ValueError):
        estimate_cost(10, 10, prompt_rate_per_1k=bad, completion_rate_per_1k=1.0)


def test_string_rate_rejected():
    with pytest.raises(TypeError):
        estimate_cost(10, 10, prompt_rate_per_1k="1", completion_rate_per_1k=1.0)
