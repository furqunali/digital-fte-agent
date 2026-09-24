"""A monotonic checkpoint store for resumable Digital FTE runs.

A long run records how far it has progressed so it can resume after a restart.
The one invariant that makes a checkpoint trustworthy is *monotonicity*: a
recorded position may only ever move forward. :class:`CheckpointStore` enforces
that -- :meth:`advance` accepts a strictly greater position and rejects any
value at or below the latest as a regression, so a stale or replayed update can
never rewind progress.

The store keeps an ordered history of accepted checkpoints (each tagged with a
sequence number and an optional label) for auditing, and :meth:`latest` returns
the current position. It holds no clock and no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass


class CheckpointRegression(Exception):
    """Raised when an advance would move a checkpoint backwards or nowhere."""

    def __init__(self, position: int, latest: int) -> None:
        super().__init__(
            f"cannot advance to {position}: not beyond latest {latest}"
        )
        self.position = position
        self.latest = latest


def _validate_position(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("position must be an integer")
    if value < 0:
        raise ValueError("position must be >= 0")
    return value


def _validate_label(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("label must be a non-empty string or None")
    return value


@dataclass(frozen=True)
class CheckpointRecord:
    """One accepted checkpoint.

    Attributes:
        position: The recorded position (monotonically increasing).
        sequence: Zero-based order in which this checkpoint was accepted.
        label: Optional caller-supplied tag for the checkpoint.
    """

    position: int
    sequence: int
    label: str | None


class CheckpointStore:
    """A forward-only store of checkpoint positions."""

    def __init__(self) -> None:
        self._records: list[CheckpointRecord] = []

    def latest(self) -> CheckpointRecord | None:
        """Return the most recent checkpoint, or ``None`` if none recorded."""
        return self._records[-1] if self._records else None

    @property
    def position(self) -> int | None:
        """The latest recorded position, or ``None`` if empty."""
        latest = self.latest()
        return None if latest is None else latest.position

    @property
    def count(self) -> int:
        """How many checkpoints have been accepted."""
        return len(self._records)

    def try_advance(
        self, position: int, label: str | None = None
    ) -> CheckpointRecord | None:
        """Advance to ``position`` if it is strictly ahead; else return ``None``.

        The non-raising counterpart to :meth:`advance`. Records nothing when the
        position does not move forward.
        """
        position = _validate_position(position)
        label = _validate_label(label)
        current = self.position
        if current is not None and position <= current:
            return None
        return self._append(position, label)

    def advance(self, position: int, label: str | None = None) -> CheckpointRecord:
        """Advance to ``position`` or raise :class:`CheckpointRegression`.

        Args:
            position: The new position; must be strictly greater than
                :meth:`latest`'s position (or any value when the store is empty).
            label: Optional tag for the checkpoint.

        Raises:
            TypeError: If ``position`` is not an ``int`` (``bool`` rejected).
            ValueError: If ``position`` is negative or ``label`` is empty.
            CheckpointRegression: If ``position`` is not beyond the latest.
        """
        position = _validate_position(position)
        label = _validate_label(label)
        current = self.position
        if current is not None and position <= current:
            raise CheckpointRegression(position, current)
        return self._append(position, label)

    def history(self) -> tuple[CheckpointRecord, ...]:
        """Return every accepted checkpoint in acceptance order."""
        return tuple(self._records)

    def _append(self, position: int, label: str | None) -> CheckpointRecord:
        record = CheckpointRecord(
            position=position, sequence=len(self._records), label=label
        )
        self._records.append(record)
        return record
