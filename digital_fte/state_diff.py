"""Structural diff between two agent-state snapshots.

Every task in a Digital FTE run is persisted as a :class:`~digital_fte.loop.LoopResult`
snapshot (see :mod:`digital_fte.state_store`). When an agent is resumed, retried, or
re-run, it is invaluable to answer a single question deterministically: *what changed
between the two snapshots?*

This module lifts that comparison into a typed, side-effect-free projection. Both
snapshots must describe the **same task** -- diffing unrelated tasks is meaningless
and is rejected. The diff is computed against the longest common prefix of the two
runs' recorded steps and events, so it correctly narrates three shapes of change:

* **progression** -- ``after`` extends ``before`` (new steps/events appended);
* **rewind** -- ``after`` is a strict prefix of ``before`` (steps/events dropped);
* **divergence** -- the runs share a prefix then differ (steps/events removed *and*
  added), e.g. after a retry took a different path.

Like :mod:`digital_fte.run_timeline`, the diff is a pure deterministic function of
its inputs -- no clocks, no I/O -- so it is safe to persist, render, or assert on.
"""
from __future__ import annotations

from dataclasses import dataclass

from digital_fte.loop import LoopEvent, LoopResult, LoopStep


def _common_prefix_length(left: tuple[object, ...], right: tuple[object, ...]) -> int:
    """Return how many leading elements ``left`` and ``right`` share."""
    length = 0
    for a, b in zip(left, right):
        if a != b:
            break
        length += 1
    return length


@dataclass(frozen=True)
class StateDiff:
    """The structural difference between two snapshots of one task's loop state.

    A diff is always oriented ``before`` -> ``after``. ``*_added`` holds entries
    present in ``after`` beyond the shared prefix; ``*_removed`` holds entries that
    were in ``before`` beyond the shared prefix and are gone in ``after``. A pure
    append yields only additions; a pure rewind yields only removals; a divergent
    retry yields both.

    Attributes:
        task_id: The shared task id of both snapshots.
        status_before: ``before.status``.
        status_after: ``after.status``.
        iterations_before: ``before.iterations``.
        iterations_after: ``after.iterations``.
        final_state_before: ``before.final_state``.
        final_state_after: ``after.final_state``.
        steps_added: Steps recorded only in ``after`` (in execution order).
        steps_removed: Steps recorded only in ``before`` (in execution order).
        events_added: Transitions recorded only in ``after`` (in execution order).
        events_removed: Transitions recorded only in ``before`` (in execution order).
    """

    task_id: str
    status_before: str
    status_after: str
    iterations_before: int
    iterations_after: int
    final_state_before: str
    final_state_after: str
    steps_added: tuple[LoopStep, ...]
    steps_removed: tuple[LoopStep, ...]
    events_added: tuple[LoopEvent, ...]
    events_removed: tuple[LoopEvent, ...]

    @property
    def iterations_delta(self) -> int:
        """Signed change in iteration count (``after - before``)."""
        return self.iterations_after - self.iterations_before

    @property
    def status_changed(self) -> bool:
        """Whether the run's terminal status differs between snapshots."""
        return self.status_before != self.status_after

    @property
    def final_state_changed(self) -> bool:
        """Whether the final state string differs between snapshots."""
        return self.final_state_before != self.final_state_after

    @property
    def is_noop(self) -> bool:
        """True when the two snapshots are structurally identical."""
        return not (
            self.status_changed
            or self.final_state_changed
            or self.iterations_delta != 0
            or self.steps_added
            or self.steps_removed
            or self.events_added
            or self.events_removed
        )

    @property
    def is_progression(self) -> bool:
        """True when ``after`` only extends ``before`` (added work, nothing dropped).

        A no-op is not a progression: something must actually have been appended.
        """
        return bool(self.events_added or self.steps_added) and not (
            self.events_removed or self.steps_removed
        )

    @property
    def is_rewind(self) -> bool:
        """True when ``after`` only drops trailing work from ``before``."""
        return bool(self.events_removed or self.steps_removed) and not (
            self.events_added or self.steps_added
        )

    @property
    def is_divergence(self) -> bool:
        """True when the runs share a prefix then both drop and add work."""
        return bool(self.events_removed or self.steps_removed) and bool(
            self.events_added or self.steps_added
        )

    @property
    def agents_engaged(self) -> tuple[str, ...]:
        """Distinct agents appearing in ``events_added``, in first-seen order."""
        seen: dict[str, None] = {}
        for event in self.events_added:
            seen.setdefault(event.agent, None)
        return tuple(seen)

    @property
    def has_changes(self) -> bool:
        """Convenience inverse of :attr:`is_noop`."""
        return not self.is_noop


def diff_states(before: LoopResult, after: LoopResult) -> StateDiff:
    """Compute the structural diff from ``before`` to ``after``.

    Both arguments must be :class:`LoopResult` snapshots of the *same* task. The
    added/removed step and event sets are derived from the longest common prefix of
    each sequence, so appends, rewinds, and divergent retries are all represented
    exactly once.

    Args:
        before: The earlier snapshot.
        after: The later snapshot to compare against ``before``.

    Returns:
        A :class:`StateDiff` describing every difference.

    Raises:
        TypeError: If either argument is not a :class:`LoopResult`.
        ValueError: If the snapshots describe different tasks.
    """
    if not isinstance(before, LoopResult):
        raise TypeError("before must be a LoopResult")
    if not isinstance(after, LoopResult):
        raise TypeError("after must be a LoopResult")
    if before.task_id != after.task_id:
        raise ValueError(
            "cannot diff snapshots of different tasks: "
            f"{before.task_id!r} != {after.task_id!r}"
        )

    step_prefix = _common_prefix_length(before.steps, after.steps)
    event_prefix = _common_prefix_length(before.events, after.events)

    return StateDiff(
        task_id=after.task_id,
        status_before=before.status,
        status_after=after.status,
        iterations_before=before.iterations,
        iterations_after=after.iterations,
        final_state_before=before.final_state,
        final_state_after=after.final_state,
        steps_added=after.steps[step_prefix:],
        steps_removed=before.steps[step_prefix:],
        events_added=after.events[event_prefix:],
        events_removed=before.events[event_prefix:],
    )


def render_diff(diff: StateDiff) -> tuple[str, ...]:
    """Render a diff into deterministic, human-readable lines.

    The first line classifies the change (no-op / progression / rewind /
    divergence) and always names the task. Subsequent lines report status and
    final-state transitions when they changed, followed by ``+``/``-`` lines for
    each added/removed transition in execution order. A no-op renders as a single
    classification line.
    """
    if diff.is_noop:
        shape = "noop"
    elif diff.is_progression:
        shape = "progression"
    elif diff.is_rewind:
        shape = "rewind"
    elif diff.is_divergence:
        shape = "divergence"
    else:
        shape = "changed"

    lines = [f"diff {diff.task_id}: {shape} ({diff.iterations_delta:+d} iterations)"]

    if diff.status_changed:
        lines.append(f"status: {diff.status_before} -> {diff.status_after}")
    if diff.final_state_changed:
        lines.append(
            f"final_state: {diff.final_state_before} -> {diff.final_state_after}"
        )
    for event in diff.events_removed:
        lines.append(
            f"- i{event.iteration} {event.agent}: "
            f"{event.input_state} -> {event.output_state}"
        )
    for event in diff.events_added:
        lines.append(
            f"+ i{event.iteration} {event.agent}: "
            f"{event.input_state} -> {event.output_state}"
        )
    return tuple(lines)
