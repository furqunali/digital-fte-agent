from dataclasses import FrozenInstanceError

import pytest

from digital_fte.priority_queue import (
    PrioritizedItem,
    PriorityQueue,
    PriorityQueueEmpty,
)


def test_min_mode_serves_smallest_first():
    q = PriorityQueue(mode="min")
    q.push("b", 5)
    q.push("a", 1)
    q.push("c", 9)
    assert [q.pop().item for _ in range(3)] == ["a", "b", "c"]


def test_max_mode_serves_largest_first():
    q = PriorityQueue(mode="max")
    q.push("b", 5)
    q.push("a", 1)
    q.push("c", 9)
    assert [q.pop().item for _ in range(3)] == ["c", "b", "a"]


def test_default_mode_is_min():
    q = PriorityQueue()
    q.push("hi", 10)
    q.push("lo", 1)
    assert q.pop().item == "lo"


def test_stable_within_equal_priority_min():
    q = PriorityQueue(mode="min")
    for name in ["first", "second", "third"]:
        q.push(name, 0)
    assert [q.pop().item for _ in range(3)] == ["first", "second", "third"]


def test_stable_within_equal_priority_max():
    q = PriorityQueue(mode="max")
    for name in ["first", "second", "third"]:
        q.push(name, 7)
    assert [q.pop().item for _ in range(3)] == ["first", "second", "third"]


def test_peek_does_not_remove():
    q = PriorityQueue()
    q.push("x", 1)
    assert q.peek().item == "x"
    assert len(q) == 1


def test_len_and_is_empty():
    q = PriorityQueue()
    assert q.is_empty is True
    q.push("x", 1)
    assert len(q) == 1
    assert q.is_empty is False


def test_pop_empty_raises():
    q = PriorityQueue()
    with pytest.raises(PriorityQueueEmpty):
        q.pop()


def test_peek_empty_raises():
    q = PriorityQueue()
    with pytest.raises(PriorityQueueEmpty):
        q.peek()


def test_drain_returns_service_order():
    q = PriorityQueue(mode="min")
    q.push("mid", 5)
    q.push("low", 1)
    q.push("high", 9)
    drained = q.drain()
    assert [p.item for p in drained] == ["low", "mid", "high"]
    assert q.is_empty


def test_push_returns_prioritized_item_with_sequence():
    q = PriorityQueue()
    first = q.push("a", 1)
    second = q.push("b", 1)
    assert isinstance(first, PrioritizedItem)
    assert first.sequence == 0
    assert second.sequence == 1


def test_float_priorities_allowed():
    q = PriorityQueue(mode="min")
    q.push("a", 1.5)
    q.push("b", 1.25)
    assert q.pop().item == "b"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        PriorityQueue(mode="fifo")


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_priority_must_be_finite(bad):
    q = PriorityQueue()
    with pytest.raises(ValueError):
        q.push("x", bad)


def test_priority_bool_rejected():
    q = PriorityQueue()
    with pytest.raises(TypeError):
        q.push("x", True)


def test_priority_non_number_rejected():
    q = PriorityQueue()
    with pytest.raises(TypeError):
        q.push("x", "high")


def test_prioritized_item_is_frozen():
    item = PrioritizedItem(item="x", priority=1.0, sequence=0)
    with pytest.raises(FrozenInstanceError):
        item.priority = 2.0  # type: ignore[misc]
