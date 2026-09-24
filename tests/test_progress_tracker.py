from dataclasses import FrozenInstanceError

import pytest

from digital_fte.progress_tracker import Progress, track_progress


def test_basic_progress():
    p = track_progress(3, 10)
    assert p.completed == 3
    assert p.total == 10
    assert p.remaining == 7
    assert p.fraction == 0.3
    assert p.percent == 30.0
    assert p.is_complete is False


def test_zero_progress():
    p = track_progress(0, 4)
    assert p.remaining == 4
    assert p.fraction == 0.0
    assert p.percent == 0.0
    assert p.is_complete is False


def test_full_progress_is_complete():
    p = track_progress(5, 5)
    assert p.remaining == 0
    assert p.fraction == 1.0
    assert p.percent == 100.0
    assert p.is_complete is True


def test_empty_total_is_complete():
    p = track_progress(0, 0)
    assert p.remaining == 0
    assert p.fraction == 1.0
    assert p.percent == 100.0
    assert p.is_complete is True


def test_fraction_and_percent_rounding():
    p = track_progress(1, 3)
    assert p.fraction == round(1 / 3, 6)
    assert p.percent == round(100 / 3, 4)


def test_completed_exceeds_total_rejected():
    with pytest.raises(ValueError):
        track_progress(6, 5)


@pytest.mark.parametrize("bad", [-1, -10])
def test_negative_rejected(bad):
    with pytest.raises(ValueError):
        track_progress(bad, 5)
    with pytest.raises(ValueError):
        track_progress(0, bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_rejected(bad):
    with pytest.raises(TypeError):
        track_progress(bad, 5)
    with pytest.raises(TypeError):
        track_progress(0, bad)


@pytest.mark.parametrize("bad", [1.5, "3", None])
def test_non_int_rejected(bad):
    with pytest.raises(TypeError):
        track_progress(bad, 5)


def test_result_is_frozen():
    p = track_progress(1, 2)
    with pytest.raises(FrozenInstanceError):
        p.completed = 2  # type: ignore[misc]


def test_progress_is_dataclass_instance():
    assert isinstance(track_progress(1, 2), Progress)
