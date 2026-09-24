from dataclasses import FrozenInstanceError

import pytest

from digital_fte.sliding_window_rate import WindowRate, count_in_window, rate_in_window


# --- count_in_window --------------------------------------------------------

def test_counts_events_in_window():
    ts = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert count_in_window(ts, now=5.0, window=3.0) == 4  # 2,3,4,5


def test_excludes_events_before_window():
    ts = [1.0, 2.0, 3.0, 4.0, 5.0]
    # window covers (2.0, 5.0] inclusive of lower bound 2.0
    assert count_in_window(ts, now=5.0, window=3.0) == 4


def test_lower_bound_inclusive():
    ts = [2.0]
    assert count_in_window(ts, now=5.0, window=3.0) == 1  # exactly at now-window


def test_upper_bound_inclusive():
    ts = [5.0]
    assert count_in_window(ts, now=5.0, window=3.0) == 1


def test_future_events_excluded():
    ts = [6.0, 7.0]
    assert count_in_window(ts, now=5.0, window=3.0) == 0


def test_empty_timestamps():
    assert count_in_window([], now=5.0, window=3.0) == 0


# --- rate_in_window ---------------------------------------------------------

def test_rate_computes_per_second():
    ts = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rate_in_window(ts, now=5.0, window=5.0)
    assert result.count == 5
    assert result.per_second == 1.0


def test_rate_per_minute():
    ts = [0.0, 5.0, 10.0]
    result = rate_in_window(ts, now=10.0, window=10.0)
    assert result.per_second == pytest.approx(0.3)
    assert result.per_minute == pytest.approx(18.0)


def test_rate_zero_when_empty():
    result = rate_in_window([], now=5.0, window=2.0)
    assert result.count == 0
    assert result.per_second == 0.0


def test_returns_window_rate():
    result = rate_in_window([1.0], now=1.0, window=1.0)
    assert isinstance(result, WindowRate)
    assert result.window == 1.0


def test_is_frozen():
    result = rate_in_window([1.0], now=1.0, window=1.0)
    with pytest.raises(FrozenInstanceError):
        result.count = 5  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_window_must_be_positive():
    with pytest.raises(ValueError):
        count_in_window([1.0], now=5.0, window=0.0)


def test_negative_window_rejected():
    with pytest.raises(ValueError):
        rate_in_window([1.0], now=5.0, window=-1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_now_rejected(bad):
    with pytest.raises(ValueError):
        count_in_window([1.0], now=bad, window=1.0)


def test_bool_now_rejected():
    with pytest.raises(TypeError):
        count_in_window([1.0], now=True, window=1.0)


def test_string_timestamps_rejected():
    with pytest.raises(TypeError):
        count_in_window("123", now=5.0, window=1.0)


def test_non_numeric_timestamp_rejected():
    with pytest.raises(TypeError):
        count_in_window([1.0, "2.0"], now=5.0, window=3.0)
