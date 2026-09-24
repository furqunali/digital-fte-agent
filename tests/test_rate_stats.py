from dataclasses import FrozenInstanceError

import pytest

from digital_fte.rate_stats import RateStats, compute_rate_stats


def test_all_success():
    s = compute_rate_stats([True, True, True])
    assert s.total == 3
    assert s.successes == 3
    assert s.failures == 0
    assert s.success_rate == 1.0
    assert s.failure_rate == 0.0
    assert s.longest_failure_streak == 0
    assert s.longest_success_streak == 3
    assert s.current_failure_streak == 0


def test_all_failure():
    s = compute_rate_stats([False, False, False, False])
    assert s.success_rate == 0.0
    assert s.failure_rate == 1.0
    assert s.longest_failure_streak == 4
    assert s.current_failure_streak == 4


def test_mixed_rates():
    s = compute_rate_stats([True, False, True, True])
    assert s.successes == 3
    assert s.failures == 1
    assert s.success_rate == 0.75
    assert s.failure_rate == 0.25


def test_longest_failure_streak_in_middle():
    s = compute_rate_stats([True, False, False, False, True])
    assert s.longest_failure_streak == 3
    assert s.current_failure_streak == 0


def test_current_failure_streak_at_end():
    s = compute_rate_stats([True, False, True, False, False])
    assert s.longest_failure_streak == 2
    assert s.current_failure_streak == 2


def test_longest_success_streak():
    s = compute_rate_stats([True, True, False, True, True, True])
    assert s.longest_success_streak == 3


def test_empty_sequence():
    s = compute_rate_stats([])
    assert s.total == 0
    assert s.successes == 0
    assert s.failures == 0
    assert s.success_rate == 0.0
    assert s.failure_rate == 0.0
    assert s.longest_failure_streak == 0
    assert s.longest_success_streak == 0
    assert s.current_failure_streak == 0


def test_single_success():
    s = compute_rate_stats([True])
    assert s.success_rate == 1.0
    assert s.longest_success_streak == 1


def test_single_failure():
    s = compute_rate_stats([False])
    assert s.failure_rate == 1.0
    assert s.current_failure_streak == 1


def test_rate_rounding():
    s = compute_rate_stats([True, False, False])
    assert s.success_rate == round(1 / 3, 4)
    assert s.failure_rate == round(2 / 3, 4)


@pytest.mark.parametrize("bad", [0, 1, "true", None])
def test_non_bool_rejected(bad):
    with pytest.raises(TypeError):
        compute_rate_stats([True, bad, False])


def test_accepts_generator():
    s = compute_rate_stats(x > 0 for x in [1, -1, 1])
    assert s.successes == 2


def test_result_is_frozen():
    s = compute_rate_stats([True])
    assert isinstance(s, RateStats)
    with pytest.raises(FrozenInstanceError):
        s.total = 5  # type: ignore[misc]
