from pathlib import Path

import pytest

from digital_fte.models import Task
from digital_fte.task_queue import QueueEmpty, QueueFull, TaskQueue


def task(task_id, title="t"):
    return Task(source=Path(f"{task_id}.md"), task_id=task_id, title=title, body="body")


def test_priority_order_highest_first():
    queue = TaskQueue()
    queue.push(task("low"), priority=1)
    queue.push(task("high"), priority=10)
    queue.push(task("mid"), priority=5)
    assert queue.task_ids() == ("high", "mid", "low")
    assert [queue.pop().task_id for _ in range(3)] == ["high", "mid", "low"]


def test_stable_fifo_within_same_priority():
    queue = TaskQueue()
    for i in range(5):
        queue.push(task(f"t{i}"), priority=3)
    # Equal priority must preserve insertion order.
    assert queue.task_ids() == ("t0", "t1", "t2", "t3", "t4")


def test_interleaved_priorities_keep_stable_ties():
    queue = TaskQueue()
    queue.push(task("a"), priority=1)
    queue.push(task("b"), priority=2)
    queue.push(task("c"), priority=1)
    queue.push(task("d"), priority=2)
    assert queue.task_ids() == ("b", "d", "a", "c")


def test_default_priority_is_zero():
    queue = TaskQueue()
    queue.push(task("first"))
    queue.push(task("second"), priority=1)
    assert queue.peek().task_id == "second"


def test_dedupe_ignores_repeated_task_id():
    queue = TaskQueue()
    assert queue.push(task("dup"), priority=1) is True
    assert queue.push(task("dup"), priority=99) is False
    # Duplicate must not change position, count, or priority.
    assert len(queue) == 1
    assert queue.task_ids() == ("dup",)


def test_membership_and_length_track_pushes_and_pops():
    queue = TaskQueue()
    queue.push(task("x"))
    assert "x" in queue and len(queue) == 1
    queue.pop()
    assert "x" not in queue and len(queue) == 0


def test_reinsert_after_pop_is_allowed():
    queue = TaskQueue()
    queue.push(task("x"))
    queue.pop()
    # Once served, the id is free again.
    assert queue.push(task("x")) is True
    assert "x" in queue


def test_capacity_rejects_when_full():
    queue = TaskQueue(capacity=2)
    queue.push(task("a"))
    queue.push(task("b"))
    assert queue.is_full
    with pytest.raises(QueueFull):
        queue.push(task("c"))


def test_capacity_duplicate_when_full_is_noop_not_error():
    queue = TaskQueue(capacity=1)
    queue.push(task("a"))
    # A duplicate must be reported as skipped, never raise QueueFull.
    assert queue.push(task("a"), priority=5) is False
    assert len(queue) == 1


def test_pop_and_peek_on_empty_raise():
    queue = TaskQueue()
    assert queue.is_empty
    with pytest.raises(QueueEmpty):
        queue.pop()
    with pytest.raises(QueueEmpty):
        queue.peek()


def test_peek_does_not_remove():
    queue = TaskQueue()
    queue.push(task("only"))
    assert queue.peek().task_id == "only"
    assert len(queue) == 1


def test_drain_returns_served_order_and_empties():
    queue = TaskQueue()
    queue.push(task("low"), priority=0)
    queue.push(task("high"), priority=9)
    assert [t.task_id for t in queue.drain()] == ["high", "low"]
    assert queue.is_empty and queue.task_ids() == ()


def test_negative_priority_orders_below_default():
    queue = TaskQueue()
    queue.push(task("normal"), priority=0)
    queue.push(task("deferred"), priority=-5)
    assert queue.task_ids() == ("normal", "deferred")


def test_invalid_capacity_rejected():
    for bad in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            TaskQueue(capacity=bad)


def test_push_type_and_value_validation():
    queue = TaskQueue()
    with pytest.raises(TypeError):
        queue.push("not a task")
    with pytest.raises(TypeError):
        queue.push(task("a"), priority=True)
    with pytest.raises(TypeError):
        queue.push(task("a"), priority="high")
    with pytest.raises(ValueError):
        queue.push(task("   "))


def test_none_capacity_is_unbounded():
    queue = TaskQueue()
    for i in range(50):
        queue.push(task(f"t{i}"))
    assert len(queue) == 50 and not queue.is_full
