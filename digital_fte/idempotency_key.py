"""Stable idempotency-key derivation for Digital FTE side effects.

The action stage of a reasoning loop frequently re-submits the *same* logical
request: a retried API call, a re-fired watcher event, a replayed task. To make
those side effects safe to repeat, downstream systems key on an *idempotency
key* -- a stable fingerprint of the request payload so that an identical payload
always yields the same key and any change yields a different one.

This module derives that key deterministically. A payload mapping is serialised
canonically -- keys sorted at every level, no insignificant whitespace -- and
hashed with SHA-256. Two payloads that differ only in key *order* therefore
produce the same key, while any change to a value or the set of keys produces a
different one. There is no randomness and no clock: the key is a pure function
of the payload (and an optional namespace).
"""
from __future__ import annotations

import hashlib
import json


def _canonical(value: object, *, path: str = "payload") -> object:
    """Return a JSON-serialisable form of ``value`` with deterministic ordering.

    Mappings are rebuilt with sorted string keys at every level so that the
    serialised form is independent of insertion order. Lists and tuples keep
    their order (which is significant). Only JSON scalar types are accepted for
    leaves; anything else is rejected up front rather than silently coerced.
    """
    if isinstance(value, dict):
        canonical: dict[str, object] = {}
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"{path}: mapping keys must be strings")
            canonical[key] = _canonical(value[key], path=f"{path}.{key}")
        # Sorting happens at serialisation time via ``sort_keys``; returning the
        # dict is enough because json.dumps sorts recursively.
        return canonical
    if isinstance(value, (list, tuple)):
        return [_canonical(item, path=f"{path}[{i}]") for i, item in enumerate(value)]
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        if isinstance(value, float):
            # NaN/inf are not representable in canonical JSON and would make the
            # key non-portable across serialisers.
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{path}: floats must be finite")
        return value
    raise TypeError(f"{path}: unsupported value type {type(value).__name__!r}")


def idempotency_key(payload: dict, *, namespace: str | None = None) -> str:
    """Return a stable SHA-256 hex idempotency key for ``payload``.

    Args:
        payload: A mapping describing the request. Keys must be strings; values
            may nest dicts, lists/tuples, and JSON scalars (``str``, ``int``,
            ``float``, ``bool``, ``None``). Floats must be finite.
        namespace: Optional prefix mixed into the hash so the same payload can
            yield distinct keys per logical context (e.g. per tenant). Must be a
            string when supplied.

    Returns:
        A 64-character lowercase hex digest. Payloads that differ only in key
        order hash identically; any value or key-set change hashes differently.

    Raises:
        TypeError: ``payload`` is not a dict, a nested key is not a string, or a
            value has an unsupported type.
        ValueError: a float value is NaN or infinite.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    if namespace is not None and not isinstance(namespace, str):
        raise TypeError("namespace must be a string or None")

    canonical = _canonical(payload)
    serialised = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    hasher = hashlib.sha256()
    if namespace is not None:
        # A length-prefixed namespace cannot collide with payload bytes.
        hasher.update(f"{len(namespace)}:{namespace}".encode("utf-8"))
    hasher.update(serialised.encode("utf-8"))
    return hasher.hexdigest()


def matches(payload: dict, key: str, *, namespace: str | None = None) -> bool:
    """Return whether ``payload`` derives to the given idempotency ``key``."""
    if not isinstance(key, str):
        raise TypeError("key must be a string")
    return idempotency_key(payload, namespace=namespace) == key
