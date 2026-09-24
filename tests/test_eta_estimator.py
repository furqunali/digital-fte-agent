from dataclasses import FrozenInstanceError

import pytest

from digital_fte.eta_estimator import EtaEstimate, estimate_eta


def test_basic_estimate():
    # 2 done in 4s -> 0.5/s; 8 remain -> 16s.
    est = estimate_eta(2, 10, 4.0)
    assert est.remaining_items == 8
    assert est.rate_per_second == pytest.approx(0.5)
    assert est.eta_seconds == pytest.approx(16.0)


def test_half_done():
    est = estimate_eta(5, 10, 10.0)
    assert est.rate_per_second == pytest.approx(0.5)
    assert est.eta_seconds == pytest.approx(10.0)


def test_complete_has_zero_eta():
    est = estimate_eta(10, 10, 20.0)
    assert est.remaining_items == 0
    assert est.eta_seconds == 0.0
    assert est.rate_per_second == pytest.approx(0.5)


def test_nothing_done_yields_none():
    est = estimate_eta(0, 10, 5.0)
    assert est.rate_per_second is None
    assert est.eta_seconds is None
    assert est.remaining_items == 10


def test_zero_elapsed_yields_none():
    est = estimate_eta(3, 10, 0.0)
    assert est.rate_per_second is None
    assert est.eta_seconds is None


def test_done_exceeds_total_rejected():
    with pytest.raises(ValueError):
        estimate_eta(11, 10, 5.0)


@pytest.mark.parametrize("bad", [-1])
def test_negative_counts_rejected(bad):
    with pytest.raises(ValueError):
        estimate_eta(bad, 10, 5.0)
    with pytest.raises(ValueError):
        estimate_eta(0, bad, 5.0)


def test_negative_elapsed_rejected():
    with pytest.raises(ValueError):
        estimate_eta(1, 10, -1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_elapsed_rejected(bad):
    with pytest.raises(ValueError):
        estimate_eta(1, 10, bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_counts_rejected(bad):
    with pytest.raises(TypeError):
        estimate_eta(bad, 10, 5.0)


def test_bool_elapsed_rejected():
    with pytest.raises(TypeError):
        estimate_eta(1, 10, True)


def test_int_elapsed_accepted():
    est = estimate_eta(2, 10, 4)
    assert est.elapsed_seconds == 4.0
    assert est.eta_seconds == pytest.approx(16.0)


def test_rounding_of_rate():
    est = estimate_eta(1, 10, 3.0)
    assert est.rate_per_second == round(1 / 3, 6)


def test_result_is_frozen():
    est = estimate_eta(1, 10, 5.0)
    assert isinstance(est, EtaEstimate)
    with pytest.raises(FrozenInstanceError):
        est.done = 2  # type: ignore[misc]
