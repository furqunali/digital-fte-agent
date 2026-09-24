"""In-process slot accounting to cap Digital FTE concurrency.

A run may want at most ``max_slots`` actions in flight at once -- open file
handles, outbound calls, child tasks. :class:`ConcurrencyLimiter` is a plain
counter of occupied slots: :meth:`acquire` claims slots when room exists and
:meth:`release` returns them. It is deliberately *not* a blocking semaphore --
it never sleeps or waits, so it stays deterministic and thread-model-free like
the rest of the package; a caller that cannot acquire decides what to do next.

The accounting is defensive on both ends: acquiring more than the free slots is
refused, and releasing more than are held raises rather than silently driving
the counter negative (which would quietly inflate the effective limit).
"""
from __future__ import annotations


class ConcurrencyLimitExceeded(Exception):
    """Raised when :meth:`ConcurrencyLimiter.acquire` cannot grant slots."""

    def __init__(self, requested: int, available: int) -> None:
        super().__init__(
            f"cannot acquire {requested} slot(s): only {available} available"
        )
        self.requested = requested
        self.available = available


def _validate_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


class ConcurrencyLimiter:
    """A counter of in-use slots bounded by ``max_slots``.

    Args:
        max_slots: The maximum number of slots that may be held at once
            (positive integer).
    """

    def __init__(self, max_slots: int) -> None:
        self.max_slots = _validate_positive_int("max_slots", max_slots)
        self._in_use = 0

    @property
    def in_use(self) -> int:
        """Slots currently held."""
        return self._in_use

    @property
    def available(self) -> int:
        """Slots still free to acquire."""
        return self.max_slots - self._in_use

    @property
    def is_full(self) -> bool:
        """True when no slots remain."""
        return self._in_use >= self.max_slots

    def try_acquire(self, n: int = 1) -> bool:
        """Claim ``n`` slots if room exists, returning success without raising.

        Charges nothing when the request cannot be satisfied, so it is safe to
        use directly as a loop guard.
        """
        n = _validate_positive_int("n", n)
        if n > self.available:
            return False
        self._in_use += n
        return True

    def acquire(self, n: int = 1) -> None:
        """Claim ``n`` slots or raise :class:`ConcurrencyLimitExceeded`.

        The raising counterpart to :meth:`try_acquire`; nothing is charged on
        failure.
        """
        n = _validate_positive_int("n", n)
        if n > self.available:
            raise ConcurrencyLimitExceeded(n, self.available)
        self._in_use += n

    def release(self, n: int = 1) -> None:
        """Return ``n`` previously held slots.

        Raises:
            ValueError: If ``n`` exceeds the slots currently in use -- an
                over-release, which would otherwise corrupt the accounting.
        """
        n = _validate_positive_int("n", n)
        if n > self._in_use:
            raise ValueError(
                f"cannot release {n} slot(s): only {self._in_use} in use"
            )
        self._in_use -= n
