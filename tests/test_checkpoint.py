from dataclasses import FrozenInstanceError

import pytest

from digital_fte.checkpoint import (
    CheckpointRecord,
    CheckpointRegression,
    CheckpointStore,
)


def test_starts_empty():
    store = CheckpointStore()
    assert store.latest() is None
    assert store.position is None
    assert store.count == 0


def test_advance_records_position():
    store = CheckpointStore()
    rec = store.advance(10)
    assert isinstance(rec, CheckpointRecord)
    assert rec.position == 10
    assert rec.sequence == 0
    assert store.position == 10


def test_multiple_forward_advances():
    store = CheckpointStore()
    store.advance(1)
    store.advance(5)
    store.advance(9)
    assert store.position == 9
    assert store.count == 3
    assert [r.sequence for r in store.history()] == [0, 1, 2]


def test_regression_rejected():
    store = CheckpointStore()
    store.advance(10)
    with pytest.raises(CheckpointRegression) as exc:
        store.advance(5)
    assert exc.value.position == 5
    assert exc.value.latest == 10
    # State unchanged.
    assert store.position == 10


def test_equal_position_rejected():
    store = CheckpointStore()
    store.advance(10)
    with pytest.raises(CheckpointRegression):
        store.advance(10)


def test_try_advance_returns_none_on_regression():
    store = CheckpointStore()
    store.advance(10)
    assert store.try_advance(5) is None
    assert store.try_advance(10) is None
    assert store.position == 10


def test_try_advance_records_on_forward():
    store = CheckpointStore()
    assert store.try_advance(3) is not None
    rec = store.try_advance(4)
    assert rec is not None
    assert rec.position == 4


def test_labels_are_stored():
    store = CheckpointStore()
    rec = store.advance(1, label="phase-1")
    assert rec.label == "phase-1"
    assert store.advance(2).label is None


def test_history_is_immutable_tuple():
    store = CheckpointStore()
    store.advance(1)
    hist = store.history()
    assert isinstance(hist, tuple)


@pytest.mark.parametrize("bad", [-1])
def test_negative_position_rejected(bad):
    store = CheckpointStore()
    with pytest.raises(ValueError):
        store.advance(bad)


@pytest.mark.parametrize("bad", [True, 1.5, "3"])
def test_bad_position_type_rejected(bad):
    store = CheckpointStore()
    with pytest.raises(TypeError):
        store.advance(bad)


def test_empty_label_rejected():
    store = CheckpointStore()
    with pytest.raises(ValueError):
        store.advance(1, label="")


def test_record_is_frozen():
    store = CheckpointStore()
    rec = store.advance(1)
    with pytest.raises(FrozenInstanceError):
        rec.position = 2  # type: ignore[misc]


def test_zero_is_valid_first_position():
    store = CheckpointStore()
    store.advance(0)
    assert store.position == 0
    with pytest.raises(CheckpointRegression):
        store.advance(0)
