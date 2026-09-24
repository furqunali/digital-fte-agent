from dataclasses import FrozenInstanceError

import pytest

from digital_fte.queue_depth import QueueDepthSummary, summarize_queue_depth


# --- core -------------------------------------------------------------------

def test_basic_summary():
    s = summarize_queue_depth([1, 2, 3, 4, 5])
    assert s.count == 5
    assert s.min == 1
    assert s.max == 5
    assert s.avg == 3.0


def test_p95_nearest_rank():
    # 20 values 1..20: rank = ceil(0.95 * 20) = 19 -> 19th smallest = 19
    s = summarize_queue_depth(list(range(1, 21)))
    assert s.p95 == 19


def test_single_sample():
    s = summarize_queue_depth([7])
    assert s.min == 7
    assert s.max == 7
    assert s.avg == 7.0
    assert s.p95 == 7


def test_all_equal():
    s = summarize_queue_depth([4, 4, 4, 4])
    assert s.min == s.max == 4
    assert s.avg == 4.0
    assert s.p95 == 4


def test_zeros_allowed():
    s = summarize_queue_depth([0, 0, 0])
    assert s.max == 0
    assert s.avg == 0.0


def test_floats():
    s = summarize_queue_depth([1.5, 2.5, 3.5])
    assert s.avg == pytest.approx(2.5)


def test_unordered_input():
    s = summarize_queue_depth([5, 1, 3, 2, 4])
    assert s.min == 1
    assert s.max == 5


def test_deterministic():
    data = [3, 1, 4, 1, 5, 9, 2, 6]
    assert summarize_queue_depth(data) == summarize_queue_depth(data)


# --- record shape -----------------------------------------------------------

def test_returns_summary():
    s = summarize_queue_depth([1, 2])
    assert isinstance(s, QueueDepthSummary)


def test_is_frozen():
    s = summarize_queue_depth([1, 2])
    with pytest.raises(FrozenInstanceError):
        s.max = 0  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_empty_rejected():
    with pytest.raises(ValueError):
        summarize_queue_depth([])


def test_negative_sample_rejected():
    with pytest.raises(ValueError):
        summarize_queue_depth([1, -2, 3])


def test_bool_sample_rejected():
    with pytest.raises(TypeError):
        summarize_queue_depth([1, True, 3])


def test_non_numeric_rejected():
    with pytest.raises(TypeError):
        summarize_queue_depth([1, "2", 3])


def test_nan_rejected():
    with pytest.raises(ValueError):
        summarize_queue_depth([1.0, float("nan")])


def test_string_rejected():
    with pytest.raises(TypeError):
        summarize_queue_depth("123")
