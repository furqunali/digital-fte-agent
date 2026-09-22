import pytest

from digital_fte.dead_letter_queue import (
    AlreadyDeadLettered,
    DeadLetter,
    DeadLetterQueue,
    DeadLetterQueueFull,
    ReasonCount,
    TaskNotDeadLettered,
)


def test_record_returns_entry_and_tracks_membership():
    dlq = DeadLetterQueue()
    entry = dlq.record("t1", "retries exhausted", attempts=3, failed_at="2026-09-22")
    assert entry == DeadLetter(
        task_id="t1",
        reason="retries exhausted",
        attempts=3,
        failed_at="2026-09-22",
        sequence=0,
    )
    assert "t1" in dlq
    assert len(dlq) == 1
    assert dlq.is_empty is False


def test_record_defaults_attempts_and_failed_at():
    dlq = DeadLetterQueue()
    entry = dlq.record("t1", "boom")
    assert entry.attempts == 1
    assert entry.failed_at is None


def test_empty_queue_state():
    dlq = DeadLetterQueue()
    assert dlq.is_empty is True
    assert dlq.is_full is False
    assert len(dlq) == 0
    assert dlq.task_ids() == ()
    assert dlq.entries() == ()
    assert dlq.reason_counts() == ()


def test_recording_same_task_twice_raises_and_keeps_original():
    dlq = DeadLetterQueue()
    dlq.record("t1", "first reason")
    with pytest.raises(AlreadyDeadLettered, match="t1"):
        dlq.record("t1", "second reason")
    # Original reason is untouched.
    assert dlq.get("t1").reason == "first reason"
    assert len(dlq) == 1


def test_entries_and_task_ids_preserve_insertion_order():
    dlq = DeadLetterQueue()
    dlq.record("b", "r")
    dlq.record("a", "r")
    dlq.record("c", "r")
    assert dlq.task_ids() == ("b", "a", "c")
    assert [e.task_id for e in dlq.entries()] == ["b", "a", "c"]
    assert [e.sequence for e in dlq.entries()] == [0, 1, 2]


def test_get_returns_record_or_raises():
    dlq = DeadLetterQueue()
    dlq.record("t1", "nope")
    assert dlq.get("t1").reason == "nope"
    with pytest.raises(TaskNotDeadLettered, match="missing"):
        dlq.get("missing")


def test_remove_pulls_entry_and_shrinks_queue():
    dlq = DeadLetterQueue()
    dlq.record("t1", "r1")
    dlq.record("t2", "r2")
    removed = dlq.remove("t1")
    assert removed.task_id == "t1"
    assert "t1" not in dlq
    assert dlq.task_ids() == ("t2",)


def test_remove_missing_raises():
    dlq = DeadLetterQueue()
    with pytest.raises(TaskNotDeadLettered, match="ghost"):
        dlq.remove("ghost")


def test_remove_then_record_same_id_allowed():
    dlq = DeadLetterQueue()
    dlq.record("t1", "first")
    dlq.remove("t1")
    # Once pulled out (e.g. requeued) the id may be dead-lettered again.
    again = dlq.record("t1", "second")
    assert again.reason == "second"
    assert again.sequence == 1  # sequence keeps advancing monotonically


def test_reason_counts_orders_by_count_then_reason():
    dlq = DeadLetterQueue()
    dlq.record("t1", "timeout")
    dlq.record("t2", "timeout")
    dlq.record("t3", "auth")
    dlq.record("t4", "auth")
    dlq.record("t5", "disk")
    counts = dlq.reason_counts()
    assert counts == (
        ReasonCount(reason="auth", count=2),
        ReasonCount(reason="timeout", count=2),
        ReasonCount(reason="disk", count=1),
    )


def test_drain_empties_queue_in_order():
    dlq = DeadLetterQueue()
    dlq.record("t1", "r1")
    dlq.record("t2", "r2")
    drained = dlq.drain()
    assert [e.task_id for e in drained] == ["t1", "t2"]
    assert dlq.is_empty is True
    assert len(dlq) == 0


def test_capacity_enforced():
    dlq = DeadLetterQueue(capacity=2)
    dlq.record("t1", "r")
    dlq.record("t2", "r")
    assert dlq.is_full is True
    with pytest.raises(DeadLetterQueueFull, match=r"capacity \(2\)"):
        dlq.record("t3", "r")
    # Removing frees a slot.
    dlq.remove("t1")
    assert dlq.is_full is False
    assert dlq.record("t3", "r").task_id == "t3"


def test_capacity_one_still_dedupes_before_full_check():
    dlq = DeadLetterQueue(capacity=1)
    dlq.record("t1", "r")
    # A duplicate id reports the dedupe error, not a capacity error.
    with pytest.raises(AlreadyDeadLettered):
        dlq.record("t1", "again")


def test_invalid_capacity_rejected():
    for bad in (0, -1, True, 1.5, "3"):
        with pytest.raises(ValueError):
            DeadLetterQueue(capacity=bad)


def test_invalid_task_id_rejected():
    dlq = DeadLetterQueue()
    for bad in ("", "   ", 123, None):
        with pytest.raises(ValueError):
            dlq.record(bad, "reason")
        with pytest.raises(ValueError):
            dlq.get(bad)
        with pytest.raises(ValueError):
            dlq.remove(bad)


def test_invalid_reason_rejected():
    dlq = DeadLetterQueue()
    for bad in ("", "   ", 123, None):
        with pytest.raises(ValueError):
            dlq.record("t1", bad)


def test_invalid_attempts_rejected():
    dlq = DeadLetterQueue()
    for bad in (0, -1, True, 1.5, "2", None):
        with pytest.raises(ValueError):
            dlq.record("t1", "reason", attempts=bad)


def test_invalid_failed_at_rejected():
    dlq = DeadLetterQueue()
    for bad in ("", "   ", 123):
        with pytest.raises(ValueError):
            dlq.record("t1", "reason", failed_at=bad)
