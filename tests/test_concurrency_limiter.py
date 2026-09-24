import pytest

from digital_fte.concurrency_limiter import (
    ConcurrencyLimitExceeded,
    ConcurrencyLimiter,
)


def test_starts_empty():
    lim = ConcurrencyLimiter(3)
    assert lim.in_use == 0
    assert lim.available == 3
    assert lim.is_full is False


def test_acquire_and_release():
    lim = ConcurrencyLimiter(2)
    lim.acquire()
    assert lim.in_use == 1
    assert lim.available == 1
    lim.release()
    assert lim.in_use == 0


def test_fill_to_capacity():
    lim = ConcurrencyLimiter(2)
    lim.acquire()
    lim.acquire()
    assert lim.is_full is True
    assert lim.available == 0


def test_try_acquire_returns_false_when_full():
    lim = ConcurrencyLimiter(1)
    assert lim.try_acquire() is True
    assert lim.try_acquire() is False
    # Nothing over-charged.
    assert lim.in_use == 1


def test_acquire_raises_when_full():
    lim = ConcurrencyLimiter(1)
    lim.acquire()
    with pytest.raises(ConcurrencyLimitExceeded) as exc:
        lim.acquire()
    assert exc.value.requested == 1
    assert exc.value.available == 0


def test_multi_slot_acquire():
    lim = ConcurrencyLimiter(5)
    assert lim.try_acquire(3) is True
    assert lim.available == 2
    assert lim.try_acquire(3) is False  # only 2 left
    assert lim.available == 2


def test_acquire_more_than_max_rejected():
    lim = ConcurrencyLimiter(3)
    with pytest.raises(ConcurrencyLimitExceeded):
        lim.acquire(4)


def test_over_release_raises():
    lim = ConcurrencyLimiter(3)
    lim.acquire()
    with pytest.raises(ValueError):
        lim.release(2)
    # State intact after the rejected release.
    assert lim.in_use == 1


def test_release_on_empty_raises():
    lim = ConcurrencyLimiter(3)
    with pytest.raises(ValueError):
        lim.release()


@pytest.mark.parametrize("bad", [0, -1])
def test_max_slots_must_be_positive(bad):
    with pytest.raises(ValueError):
        ConcurrencyLimiter(bad)


@pytest.mark.parametrize("bad", [True, 1.5, "2"])
def test_max_slots_type_rejected(bad):
    with pytest.raises(TypeError):
        ConcurrencyLimiter(bad)


@pytest.mark.parametrize("bad", [0, -1])
def test_acquire_n_must_be_positive(bad):
    lim = ConcurrencyLimiter(3)
    with pytest.raises(ValueError):
        lim.try_acquire(bad)


def test_full_lifecycle_repeats():
    lim = ConcurrencyLimiter(2)
    for _ in range(3):
        lim.acquire(2)
        assert lim.is_full
        lim.release(2)
        assert lim.in_use == 0
