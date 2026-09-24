import pytest

from digital_fte.percentiles import p50, p90, p99, percentile


# --- core -------------------------------------------------------------------

def test_median_odd_sample():
    assert p50([1, 2, 3, 4, 5]) == 3


def test_p90_of_ten():
    # nearest-rank: rank = ceil(0.9 * 10) = 9 -> 9th smallest
    assert p90(list(range(1, 11))) == 9


def test_p99_returns_top():
    assert p99(list(range(1, 101))) == 99


def test_q_zero_is_minimum():
    assert percentile([5, 1, 9, 3], 0) == 1


def test_q_hundred_is_maximum():
    assert percentile([5, 1, 9, 3], 100) == 9


def test_single_element():
    assert percentile([42], 50) == 42
    assert percentile([42], 0) == 42
    assert percentile([42], 100) == 42


def test_unsorted_input_handled():
    assert percentile([3, 1, 2], 50) == 2


def test_arbitrary_quantile():
    # rank = ceil(0.25 * 8) = 2 -> 2nd smallest
    assert percentile([10, 20, 30, 40, 50, 60, 70, 80], 25) == 20


def test_deterministic():
    sample = [4, 8, 15, 16, 23, 42]
    assert percentile(sample, 75) == percentile(sample, 75)


def test_floats():
    assert percentile([0.1, 0.5, 0.9], 50) == 0.5


# --- validation -------------------------------------------------------------

def test_empty_sample_rejected():
    with pytest.raises(ValueError):
        percentile([], 50)


@pytest.mark.parametrize("bad", [-1, 101, float("nan")])
def test_q_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        percentile([1, 2, 3], bad)


def test_bool_q_rejected():
    with pytest.raises(TypeError):
        percentile([1, 2, 3], True)


def test_non_numeric_value_rejected():
    with pytest.raises(TypeError):
        percentile([1, "2", 3], 50)


def test_nan_value_rejected():
    with pytest.raises(ValueError):
        percentile([1.0, float("nan"), 3.0], 50)


def test_inf_value_rejected():
    with pytest.raises(ValueError):
        percentile([1.0, float("inf")], 50)


def test_string_sample_rejected():
    with pytest.raises(TypeError):
        percentile("123", 50)
