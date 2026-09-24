"""A token budget tracker for LLM-driven Digital FTE runs.

A run has a finite pool of model tokens to spend. Before making a call the loop
often wants to *reserve* an optimistic estimate, then *consume* the true amount
once the call returns (which may be less). An optional ``safety_reserve`` carves
off a floor of tokens that can never be reserved or consumed, leaving headroom
for a final summary or a graceful shutdown.

The tracker is a small deterministic state machine over integer counts: there is
no clock and no randomness, so a sequence of operations always leaves it in the
same state. Overspending raises :class:`BudgetExceeded` rather than silently
going negative.
"""
from __future__ import annotations

from dataclasses import dataclass


def _require_count(name: str, value: object, *, minimum: int = 0) -> int:
    """Return ``value`` as an int that is at least ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


class BudgetExceeded(Exception):
    """Raised when an operation would spend more tokens than remain.

    :attr:`requested` is the amount asked for and :attr:`available` is what was
    actually free at the time.
    """

    def __init__(self, requested: int, available: int) -> None:
        super().__init__(
            f"token budget exceeded: requested {requested}, only {available} available"
        )
        self.requested = requested
        self.available = available


@dataclass(frozen=True)
class BudgetSnapshot:
    """An immutable view of a budget's counters at one moment."""

    total: int
    safety_reserve: int
    consumed: int
    reserved: int
    remaining: int


class TokenBudget:
    """Track token reservations and consumption against a fixed pool.

    Args:
        total: Total tokens in the pool (``>= 0``).
        safety_reserve: Tokens held back and never spendable (``>= 0``); must
            not exceed ``total``.

    ``remaining`` is ``total - safety_reserve - consumed - reserved``. Reserve
    tokens optimistically with :meth:`reserve`, release them with
    :meth:`release`, record actual usage with :meth:`consume`, and combine the
    two with :meth:`commit`.
    """

    def __init__(self, total: int, *, safety_reserve: int = 0) -> None:
        self._total = _require_count("total", total)
        self._safety_reserve = _require_count("safety_reserve", safety_reserve)
        if self._safety_reserve > self._total:
            raise ValueError("safety_reserve must not exceed total")
        self._consumed = 0
        self._reserved = 0

    # -- introspection -------------------------------------------------------

    @property
    def total(self) -> int:
        """The full token pool, including the safety reserve."""
        return self._total

    @property
    def safety_reserve(self) -> int:
        """Tokens permanently held back and never spendable."""
        return self._safety_reserve

    @property
    def usable(self) -> int:
        """Tokens spendable in principle (``total - safety_reserve``)."""
        return self._total - self._safety_reserve

    @property
    def consumed(self) -> int:
        """Tokens recorded as actually used."""
        return self._consumed

    @property
    def reserved(self) -> int:
        """Tokens currently held by outstanding reservations."""
        return self._reserved

    def remaining(self) -> int:
        """Return tokens still free to reserve or consume."""
        return self.usable - self._consumed - self._reserved

    def snapshot(self) -> BudgetSnapshot:
        """Return an immutable snapshot of all counters."""
        return BudgetSnapshot(
            total=self._total,
            safety_reserve=self._safety_reserve,
            consumed=self._consumed,
            reserved=self._reserved,
            remaining=self.remaining(),
        )

    # -- operations ----------------------------------------------------------

    def reserve(self, amount: int) -> int:
        """Hold ``amount`` tokens tentatively; return the new remaining.

        Raises :class:`BudgetExceeded` if fewer than ``amount`` tokens are free.
        """
        amount = _require_count("amount", amount)
        available = self.remaining()
        if amount > available:
            raise BudgetExceeded(amount, available)
        self._reserved += amount
        return self.remaining()

    def release(self, amount: int) -> int:
        """Give back ``amount`` previously reserved tokens; return remaining.

        Raises :class:`ValueError` if ``amount`` exceeds what is reserved.
        """
        amount = _require_count("amount", amount)
        if amount > self._reserved:
            raise ValueError("cannot release more than is reserved")
        self._reserved -= amount
        return self.remaining()

    def consume(self, amount: int) -> int:
        """Record ``amount`` tokens as spent from the free pool; return remaining.

        This spends against :meth:`remaining` (it does not touch reservations).
        To spend against a reservation use :meth:`commit`. Raises
        :class:`BudgetExceeded` when insufficient tokens are free.
        """
        amount = _require_count("amount", amount)
        available = self.remaining()
        if amount > available:
            raise BudgetExceeded(amount, available)
        self._consumed += amount
        return self.remaining()

    def commit(self, reserved_amount: int, actual_amount: int) -> int:
        """Release a reservation and record actual usage atomically.

        Releases ``reserved_amount`` reserved tokens, then consumes
        ``actual_amount`` (which may be smaller or larger than the reservation).
        Either the whole operation succeeds or the tracker is left unchanged.
        """
        reserved_amount = _require_count("reserved_amount", reserved_amount)
        actual_amount = _require_count("actual_amount", actual_amount)
        if reserved_amount > self._reserved:
            raise ValueError("cannot release more than is reserved")
        # Check the consume half against the state *after* the release before
        # mutating anything, so a failure leaves counters untouched.
        available_after_release = self.remaining() + reserved_amount
        if actual_amount > available_after_release:
            raise BudgetExceeded(actual_amount, available_after_release)
        self._reserved -= reserved_amount
        self._consumed += actual_amount
        return self.remaining()
