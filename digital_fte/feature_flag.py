"""Deterministic feature-flag evaluation for staged Digital FTE rollouts.

A flag is evaluated for a *subject* (an agent id, tenant, task id) from three
inputs: an explicit block list, an explicit allow list, and a percentage
rollout. Precedence is fixed and checked in that order -- a blocked subject is
always off, an allow-listed subject is always on, and everyone else is bucketed
by the rollout percentage.

The rollout decision is stable across processes and runs because it hashes the
subject id with :mod:`hashlib` (SHA-256) rather than the salted built-in
``hash``. Each subject maps to a fixed bucket in ``0..9999``; a rollout of
``p`` percent admits every subject whose bucket is below ``p / 100 * 10000``.
The mapping is monotonic in the percentage, so raising the rollout only ever
adds subjects -- a subject enabled at 10% stays enabled at 20%.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass

#: Number of buckets a subject id can hash into.
BUCKETS = 10_000

# Reasons a decision can carry, for telemetry.
REASON_BLOCKLIST = "blocklist"
REASON_ALLOWLIST = "allowlist"
REASON_ROLLOUT = "rollout"
REASON_EXCLUDED = "rollout_excluded"


def _validate_subject(subject_id: object) -> str:
    if not isinstance(subject_id, str) or not subject_id:
        raise ValueError("subject_id must be a non-empty string")
    return subject_id


def _validate_percent(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("rollout_percent must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError("rollout_percent must not be NaN")
    if math.isinf(number):
        raise ValueError("rollout_percent must be finite")
    if not 0.0 <= number <= 100.0:
        raise ValueError("rollout_percent must be within 0..100")
    return number


def _as_str_set(name: str, values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        return frozenset()
    result = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must contain non-empty strings")
        result.add(value)
    return frozenset(result)


def bucket_of(subject_id: str) -> int:
    """Return the stable ``0..9999`` rollout bucket for ``subject_id``.

    Uses a SHA-256 digest so the bucket is identical across processes, Python
    versions, and runs -- unlike the salted built-in ``hash``.
    """
    subject_id = _validate_subject(subject_id)
    digest = hashlib.sha256(subject_id.encode("utf-8")).digest()
    return int.from_bytes(digest, "big") % BUCKETS


@dataclass(frozen=True)
class FlagDecision:
    """The outcome of evaluating a flag for one subject.

    Attributes:
        subject_id: The subject the flag was evaluated for.
        enabled: Whether the flag is on for this subject.
        reason: Why -- one of ``"blocklist"``, ``"allowlist"``, ``"rollout"``,
            or ``"rollout_excluded"``.
        bucket: The subject's rollout bucket in ``0..9999``.
    """

    subject_id: str
    enabled: bool
    reason: str
    bucket: int


def evaluate_flag(
    subject_id: str,
    rollout_percent: float,
    *,
    allowlist: Iterable[str] | None = None,
    blocklist: Iterable[str] | None = None,
) -> FlagDecision:
    """Evaluate a feature flag for ``subject_id``.

    Args:
        subject_id: The subject to evaluate (non-empty string).
        rollout_percent: Percentage of subjects to enable, ``0..100``.
        allowlist: Subjects forced on regardless of the rollout.
        blocklist: Subjects forced off; takes precedence over ``allowlist``.

    Returns:
        A :class:`FlagDecision` with the outcome, the reason, and the bucket.

    Raises:
        TypeError: If ``rollout_percent`` is not a real number.
        ValueError: If ``subject_id`` is empty, ``rollout_percent`` is out of
            range or non-finite, or a list contains a non-string/empty entry.
    """
    subject_id = _validate_subject(subject_id)
    rollout_percent = _validate_percent(rollout_percent)
    allow = _as_str_set("allowlist", allowlist)
    block = _as_str_set("blocklist", blocklist)
    bucket = bucket_of(subject_id)

    if subject_id in block:
        return FlagDecision(subject_id, False, REASON_BLOCKLIST, bucket)
    if subject_id in allow:
        return FlagDecision(subject_id, True, REASON_ALLOWLIST, bucket)

    threshold = rollout_percent / 100.0 * BUCKETS
    if bucket < threshold:
        return FlagDecision(subject_id, True, REASON_ROLLOUT, bucket)
    return FlagDecision(subject_id, False, REASON_EXCLUDED, bucket)
