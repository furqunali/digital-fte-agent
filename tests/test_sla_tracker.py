from dataclasses import FrozenInstanceError

import pytest

from digital_fte.sla_tracker import SLAReport, track_sla


# --- core -------------------------------------------------------------------

def test_counts_breaches():
    report = track_sla([100, 150, 250, 300], threshold=200)
    assert report.total == 4
    assert report.breaches == 2


def test_breach_rate():
    report = track_sla([100, 300], threshold=200)
    assert report.breach_rate == 0.5


def test_compliance_complements_breach():
    report = track_sla([100, 300, 300, 300], threshold=200)
    assert report.breaches == 3
    assert report.compliant == 1
    assert report.compliance_rate == pytest.approx(0.25)


def test_threshold_exactly_is_compliant():
    report = track_sla([200, 200], threshold=200)
    assert report.breaches == 0


def test_all_compliant():
    report = track_sla([10, 20, 30], threshold=100)
    assert report.breaches == 0
    assert report.breach_rate == 0.0
    assert report.compliance_rate == 1.0


def test_all_breach():
    report = track_sla([300, 400], threshold=200)
    assert report.breaches == 2
    assert report.breach_rate == 1.0


def test_empty_batch():
    report = track_sla([], threshold=200)
    assert report.total == 0
    assert report.breaches == 0
    assert report.breach_rate == 0.0
    assert report.compliance_rate == 1.0


def test_floats():
    report = track_sla([0.1, 0.25, 0.3], threshold=0.2)
    assert report.breaches == 2


def test_deterministic():
    data = [1, 2, 3, 4, 5]
    assert track_sla(data, threshold=3) == track_sla(data, threshold=3)


# --- record shape -----------------------------------------------------------

def test_returns_report():
    report = track_sla([1], threshold=1)
    assert isinstance(report, SLAReport)
    assert report.threshold == 1


def test_is_frozen():
    report = track_sla([1], threshold=1)
    with pytest.raises(FrozenInstanceError):
        report.breaches = 5  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_threshold_must_be_positive():
    with pytest.raises(ValueError):
        track_sla([1, 2], threshold=0)


def test_negative_threshold_rejected():
    with pytest.raises(ValueError):
        track_sla([1, 2], threshold=-1)


def test_negative_latency_rejected():
    with pytest.raises(ValueError):
        track_sla([1, -2], threshold=5)


def test_bool_latency_rejected():
    with pytest.raises(TypeError):
        track_sla([1, True], threshold=5)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_threshold_rejected(bad):
    with pytest.raises(ValueError):
        track_sla([1], threshold=bad)


def test_string_latencies_rejected():
    with pytest.raises(TypeError):
        track_sla("123", threshold=5)
