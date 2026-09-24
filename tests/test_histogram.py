from dataclasses import FrozenInstanceError

import pytest

from digital_fte.histogram import Histogram, histogram


# --- core -------------------------------------------------------------------

def test_basic_bucketing():
    h = histogram([0.5, 1.5, 2.5], low=0.0, high=3.0, bins=3)
    assert h.counts == (1, 1, 1)


def test_edges_computed():
    h = histogram([], low=0.0, high=10.0, bins=5)
    assert h.edges == (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)
    assert h.width == 2.0


def test_bins_and_total():
    h = histogram([1, 1, 2, 3], low=0.0, high=4.0, bins=4)
    assert h.bins == 4
    assert h.total == 4


def test_lower_edge_inclusive():
    h = histogram([0.0], low=0.0, high=4.0, bins=4)
    assert h.counts[0] == 1


def test_upper_edge_in_last_bin():
    h = histogram([4.0], low=0.0, high=4.0, bins=4)
    assert h.counts[-1] == 1
    assert h.overflow == 0


def test_bin_boundary_is_half_open():
    # value exactly on an internal edge goes to the upper bin
    h = histogram([2.0], low=0.0, high=4.0, bins=4)
    assert h.counts == (0, 0, 1, 0)


def test_underflow():
    h = histogram([-1.0, -5.0, 1.0], low=0.0, high=4.0, bins=4)
    assert h.underflow == 2
    assert sum(h.counts) == 1


def test_overflow():
    h = histogram([5.0, 10.0, 1.0], low=0.0, high=4.0, bins=4)
    assert h.overflow == 2
    assert sum(h.counts) == 1


def test_empty_sample():
    h = histogram([], low=0.0, high=4.0, bins=4)
    assert h.counts == (0, 0, 0, 0)
    assert h.total == 0


def test_single_bin():
    h = histogram([1, 2, 3], low=0.0, high=4.0, bins=1)
    assert h.counts == (3,)


# --- record shape -----------------------------------------------------------

def test_returns_histogram():
    h = histogram([1], low=0.0, high=4.0, bins=2)
    assert isinstance(h, Histogram)


def test_is_frozen():
    h = histogram([1], low=0.0, high=4.0, bins=2)
    with pytest.raises(FrozenInstanceError):
        h.width = 1.0  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_high_must_exceed_low():
    with pytest.raises(ValueError):
        histogram([1], low=4.0, high=4.0, bins=2)
    with pytest.raises(ValueError):
        histogram([1], low=5.0, high=4.0, bins=2)


def test_bins_must_be_positive():
    with pytest.raises(ValueError):
        histogram([1], low=0.0, high=4.0, bins=0)


def test_bins_must_be_int():
    with pytest.raises(TypeError):
        histogram([1], low=0.0, high=4.0, bins=2.5)


def test_bool_bins_rejected():
    with pytest.raises(TypeError):
        histogram([1], low=0.0, high=4.0, bins=True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_bound_rejected(bad):
    with pytest.raises(ValueError):
        histogram([1], low=0.0, high=bad, bins=2)


def test_non_numeric_sample_value_rejected():
    with pytest.raises(TypeError):
        histogram([1, "2"], low=0.0, high=4.0, bins=2)
