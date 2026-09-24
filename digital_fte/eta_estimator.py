"""Rate-based ETA estimation for a Digital FTE batch.

Given how many items are done, how many there are in total, and how much time
has elapsed, :func:`estimate_eta` projects the seconds still required assuming
the observed average throughput holds. It is a pure function: time is supplied
by the caller as ``elapsed_seconds`` rather than read from a clock, so the
estimate is fully reproducible in tests.

The estimate is intentionally conservative about the unknowable. Until at least
one item has completed *and* some time has passed there is no rate to project
from, so the ETA (and the rate) are reported as ``None`` rather than as a
fabricated number.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_RATE_PLACES = 6
_ETA_PLACES = 4


def _validate_count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _validate_elapsed(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("elapsed_seconds must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError("elapsed_seconds must not be NaN")
    if math.isinf(number):
        raise ValueError("elapsed_seconds must be finite")
    if number < 0.0:
        raise ValueError("elapsed_seconds must be >= 0")
    return number


@dataclass(frozen=True)
class EtaEstimate:
    """An immutable ETA projection.

    Attributes:
        done: Items completed so far.
        total: Total items to process.
        elapsed_seconds: Time spent so far.
        remaining_items: ``total - done``.
        rate_per_second: Observed throughput ``done / elapsed_seconds``, or
            ``None`` when it cannot yet be measured (no items done, or no time
            elapsed).
        eta_seconds: Projected seconds until completion; ``0.0`` when nothing
            remains, and ``None`` when no rate is available to project from.
    """

    done: int
    total: int
    elapsed_seconds: float
    remaining_items: int
    rate_per_second: float | None
    eta_seconds: float | None


def estimate_eta(done: int, total: int, elapsed_seconds: float) -> EtaEstimate:
    """Estimate the seconds remaining from progress and elapsed time.

    Args:
        done: Items completed so far (non-negative integer, ``<= total``).
        total: Total items to process (non-negative integer).
        elapsed_seconds: Non-negative, finite seconds spent so far.

    Returns:
        An :class:`EtaEstimate`. ``eta_seconds`` is ``0.0`` when the work is
        already finished and ``None`` when no throughput can be measured yet.

    Raises:
        TypeError: If ``done``/``total`` are not ints or ``elapsed_seconds`` is
            not a real number (``bool`` is rejected).
        ValueError: On negative values, non-finite ``elapsed_seconds``, or
            ``done > total``.
    """
    done = _validate_count("done", done)
    total = _validate_count("total", total)
    elapsed_seconds = _validate_elapsed(elapsed_seconds)
    if done > total:
        raise ValueError("done must not exceed total")

    remaining = total - done

    if done == 0 or elapsed_seconds == 0.0:
        # No throughput can be measured yet.
        rate: float | None = None
        eta: float | None = None
    else:
        rate = done / elapsed_seconds
        eta = 0.0 if remaining == 0 else remaining / rate

    return EtaEstimate(
        done=done,
        total=total,
        elapsed_seconds=elapsed_seconds,
        remaining_items=remaining,
        rate_per_second=None if rate is None else round(rate, _RATE_PLACES),
        eta_seconds=None if eta is None else round(eta, _ETA_PLACES),
    )
