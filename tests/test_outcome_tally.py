import pytest

from digital_fte.outcome_tally import (
    FAILURE,
    OUTCOMES,
    RETRY,
    SUCCESS,
    Tally,
    tally,
)


def test_basic_counts():
    t = tally([SUCCESS, SUCCESS, FAILURE, RETRY])
    assert t.success == 2
    assert t.failure == 1
    assert t.retry == 1
    assert t.total == 4


def test_rates_sum_to_one():
    t = tally([SUCCESS, FAILURE, RETRY, SUCCESS])
    assert t.success_rate == 0.5
    assert t.failure_rate == 0.25
    assert t.retry_rate == 0.25
    assert pytest.approx(t.success_rate + t.failure_rate + t.retry_rate) == 1.0


def test_all_success():
    t = tally([SUCCESS, SUCCESS, SUCCESS])
    assert t.success_rate == 1.0
    assert t.failure_rate == 0.0


def test_empty_is_all_zero():
    t = tally([])
    assert t.total == 0
    assert t.success == t.failure == t.retry == 0
    assert t.success_rate == 0.0
    assert t.failure_rate == 0.0
    assert t.retry_rate == 0.0


def test_counts_property():
    t = tally([SUCCESS, RETRY])
    assert t.counts == {SUCCESS: 1, FAILURE: 0, RETRY: 1}


def test_returns_tally_instance():
    assert isinstance(tally([SUCCESS]), Tally)


def test_accepts_generator():
    t = tally(o for o in [SUCCESS, FAILURE])
    assert t.total == 2


def test_only_retries():
    t = tally([RETRY, RETRY])
    assert t.retry == 2
    assert t.retry_rate == 1.0


def test_unknown_outcome_rejected():
    with pytest.raises(ValueError):
        tally([SUCCESS, "cancelled"])


def test_non_string_outcome_rejected():
    with pytest.raises(TypeError):
        tally([SUCCESS, 1])


def test_outcomes_constant():
    assert OUTCOMES == (SUCCESS, FAILURE, RETRY)


def test_tally_is_frozen():
    from dataclasses import FrozenInstanceError

    t = tally([SUCCESS])
    with pytest.raises(FrozenInstanceError):
        t.success = 99  # type: ignore[misc]


def test_large_mixed_sequence():
    outcomes = [SUCCESS] * 70 + [FAILURE] * 20 + [RETRY] * 10
    t = tally(outcomes)
    assert t.total == 100
    assert t.success_rate == 0.7
    assert t.failure_rate == 0.2
    assert t.retry_rate == 0.1
