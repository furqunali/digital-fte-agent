from dataclasses import FrozenInstanceError

import pytest

from digital_fte.throughput_meter import Throughput, throughput


# --- core -------------------------------------------------------------------

def test_basic_rate():
    result = throughput(100, 10.0)
    assert result.per_second == 10.0


def test_per_minute():
    result = throughput(60, 60.0)
    assert result.per_second == 1.0
    assert result.per_minute == 60.0


def test_seconds_per_item():
    result = throughput(4, 8.0)
    assert result.seconds_per_item == 2.0


def test_zero_items_zero_rate():
    result = throughput(0, 5.0)
    assert result.per_second == 0.0
    assert result.seconds_per_item == 0.0


def test_fractional_rate():
    result = throughput(1, 4.0)
    assert result.per_second == 0.25


def test_deterministic():
    assert throughput(7, 3.0) == throughput(7, 3.0)


# --- record shape -----------------------------------------------------------

def test_returns_throughput():
    result = throughput(10, 2.0)
    assert isinstance(result, Throughput)
    assert result.items == 10
    assert result.elapsed == 2.0


def test_is_frozen():
    result = throughput(10, 2.0)
    with pytest.raises(FrozenInstanceError):
        result.items = 5  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_negative_items_rejected():
    with pytest.raises(ValueError):
        throughput(-1, 5.0)


def test_float_items_rejected():
    with pytest.raises(TypeError):
        throughput(1.5, 5.0)


def test_bool_items_rejected():
    with pytest.raises(TypeError):
        throughput(True, 5.0)


def test_zero_elapsed_rejected():
    with pytest.raises(ValueError):
        throughput(10, 0.0)


def test_negative_elapsed_rejected():
    with pytest.raises(ValueError):
        throughput(10, -1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_elapsed_rejected(bad):
    with pytest.raises(ValueError):
        throughput(10, bad)


def test_string_elapsed_rejected():
    with pytest.raises(TypeError):
        throughput(10, "5")
