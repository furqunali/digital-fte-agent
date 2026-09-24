"""Structured JSONL audit-log formatting with schema validation.

A Digital FTE needs a durable, machine-readable record of what it did: which
agent acted on which iteration, how the state changed, and how the run
terminated. This module serialises those records as **JSON Lines** (JSONL) --
one self-describing JSON object per line -- and validates every line against an
explicit schema on the way both out (formatting) and in (parsing).

The record shape is a superset of a
:class:`~digital_fte.run_timeline.TimelineEvent`: each line additionally carries
a schema-version tag (``v``) so that a log written today can be recognised, and
rejected with a clear error, by a future reader that only understands a
different version.

Design mirrors the rest of the package: frozen dataclasses with explicit
``__post_init__`` validation, dependency-free logic, and -- for whole-document
parsing -- a *collect every error* mode (:func:`validate_jsonl`) alongside a
*fail fast* mode (:func:`parse_jsonl`).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from digital_fte.run_timeline import (
    AGENT_ACTED,
    TIMELINE_KINDS,
    TimelineEvent,
    build_timeline,
)

#: Current on-disk schema version. Bump when the record shape changes
#: incompatibly; older readers will then reject the newer lines rather than
#: silently misinterpreting them.
AUDIT_SCHEMA_VERSION = 1

#: The JSON keys of an audit record, in canonical serialisation order. Keeping
#: the order fixed makes emitted lines byte-stable and therefore diffable.
_FIELD_ORDER: tuple[str, ...] = (
    "v",
    "seq",
    "iteration",
    "kind",
    "agent",
    "from_state",
    "to_state",
    "changed",
)


class AuditLogError(ValueError):
    """A structured audit line could not be parsed or failed validation.

    Attributes:
        message: Human-readable description of the problem.
        line_no: 1-based line number the error refers to, or ``None`` when the
            error is not tied to a specific line.
    """

    def __init__(self, message: str, line_no: int | None = None) -> None:
        self.message = message
        self.line_no = line_no
        prefix = f"line {line_no}: " if line_no is not None else ""
        super().__init__(f"{prefix}{message}")


def _require_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditLogError(f"{name} must be an integer")
    return value


@dataclass(frozen=True)
class AuditRecord:
    """A single validated audit-log entry.

    The invariants enforced here match those of
    :class:`~digital_fte.run_timeline.TimelineEvent` so that a timeline and its
    serialised audit log can never disagree:

    * ``seq`` and ``iteration`` are non-negative integers (``bool`` rejected).
    * ``kind`` is one of :data:`~digital_fte.run_timeline.TIMELINE_KINDS`.
    * ``agent_acted`` records name an ``agent`` and have ``changed`` exactly
      reflect ``from_state != to_state``; every other kind leaves ``agent``
      unset.
    * ``version`` matches :data:`AUDIT_SCHEMA_VERSION`.
    """

    seq: int
    iteration: int
    kind: str
    agent: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    changed: bool = False
    version: int = AUDIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_int(self.seq, "seq")
        if self.seq < 0:
            raise AuditLogError("seq must be non-negative")
        _require_int(self.iteration, "iteration")
        if self.iteration < 0:
            raise AuditLogError("iteration must be non-negative")
        if self.kind not in TIMELINE_KINDS:
            raise AuditLogError(f"unknown kind: {self.kind!r}")
        if not isinstance(self.changed, bool):
            raise AuditLogError("changed must be a boolean")
        _require_int(self.version, "version")
        if self.version != AUDIT_SCHEMA_VERSION:
            raise AuditLogError(
                f"unsupported schema version {self.version}; "
                f"expected {AUDIT_SCHEMA_VERSION}"
            )
        for name in ("agent", "from_state", "to_state"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise AuditLogError(f"{name} must be a string or null")
        if self.kind == AGENT_ACTED:
            if self.agent is None:
                raise AuditLogError("agent_acted records require an agent")
            if self.changed != (self.from_state != self.to_state):
                raise AuditLogError(
                    "changed must reflect from_state != to_state"
                )
        elif self.agent is not None:
            raise AuditLogError(f"{self.kind} records must not name an agent")

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-ready mapping for this record."""
        return {
            "v": self.version,
            "seq": self.seq,
            "iteration": self.iteration,
            "kind": self.kind,
            "agent": self.agent,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "changed": self.changed,
        }

    def to_jsonl(self) -> str:
        """Serialise to a single JSONL line (no trailing newline).

        Keys are emitted in :data:`_FIELD_ORDER`; non-ASCII state names are kept
        verbatim (``ensure_ascii=False``) so the log stays readable.
        """
        return json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":")
        )


def record_from_timeline_event(event: TimelineEvent) -> AuditRecord:
    """Lift a :class:`TimelineEvent` into an :class:`AuditRecord`.

    Raises:
        TypeError: If ``event`` is not a :class:`TimelineEvent`.
    """
    if not isinstance(event, TimelineEvent):
        raise TypeError("event must be a TimelineEvent")
    return AuditRecord(
        seq=event.sequence,
        iteration=event.iteration,
        kind=event.kind,
        agent=event.agent,
        from_state=event.from_state,
        to_state=event.to_state,
        changed=event.changed,
    )


def build_audit_records(result: object) -> tuple[AuditRecord, ...]:
    """Project a :class:`~digital_fte.loop.LoopResult` to audit records.

    A thin, validated bridge over :func:`~digital_fte.run_timeline.build_timeline`
    -- it inherits that function's ``TypeError``/``ValueError`` for a malformed
    or non-terminal result.
    """
    return tuple(
        record_from_timeline_event(event) for event in build_timeline(result)
    )


def format_audit_log(records: Iterable[AuditRecord]) -> str:
    """Serialise records to a JSONL document terminated by a trailing newline.

    An empty iterable yields the empty string (not a lone newline), so an empty
    log round-trips cleanly through :func:`parse_jsonl`.

    Raises:
        TypeError: If any item is not an :class:`AuditRecord`.
    """
    lines: list[str] = []
    for record in records:
        if not isinstance(record, AuditRecord):
            raise TypeError("every item must be an AuditRecord")
        lines.append(record.to_jsonl())
    return "".join(f"{line}\n" for line in lines)


def _record_from_mapping(data: object, line_no: int | None) -> AuditRecord:
    """Build and validate an :class:`AuditRecord` from a decoded JSON object."""
    if not isinstance(data, dict):
        raise AuditLogError(
            f"record must be a JSON object, got {type(data).__name__}",
            line_no,
        )
    unknown = set(data) - set(_FIELD_ORDER)
    if unknown:
        joined = ", ".join(sorted(str(k) for k in unknown))
        raise AuditLogError(f"unknown field(s): {joined}", line_no)
    if "v" not in data:
        raise AuditLogError("missing required field: v", line_no)
    for required in ("seq", "iteration", "kind"):
        if required not in data:
            raise AuditLogError(f"missing required field: {required}", line_no)
    try:
        return AuditRecord(
            seq=data["seq"],
            iteration=data["iteration"],
            kind=data["kind"],
            agent=data.get("agent"),
            from_state=data.get("from_state"),
            to_state=data.get("to_state"),
            changed=data.get("changed", False),
            version=data["v"],
        )
    except AuditLogError as exc:
        # Re-raise with the line number attached for actionable diagnostics.
        raise AuditLogError(exc.message, line_no) from exc


def parse_jsonl_line(line: str, line_no: int | None = None) -> AuditRecord:
    """Parse and validate a single JSONL line into an :class:`AuditRecord`.

    Raises:
        AuditLogError: If the line is blank, is not valid JSON, or fails schema
            validation.
    """
    if not isinstance(line, str):
        raise AuditLogError(
            f"line must be a string, got {type(line).__name__}", line_no
        )
    stripped = line.strip()
    if not stripped:
        raise AuditLogError("line is blank", line_no)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AuditLogError(f"invalid JSON: {exc.msg}", line_no) from exc
    return _record_from_mapping(data, line_no)


def _iter_content_lines(text: str) -> Iterable[tuple[int, str]]:
    """Yield ``(line_no, raw_line)`` pairs, skipping blank/whitespace lines."""
    for index, raw in enumerate(text.splitlines(), start=1):
        if raw.strip():
            yield index, raw


def parse_jsonl(text: str) -> tuple[AuditRecord, ...]:
    """Parse a whole JSONL document, failing fast on the first bad line.

    Blank and whitespace-only lines (including a trailing newline) are ignored,
    matching the output of :func:`format_audit_log`.

    Raises:
        AuditLogError: On the first line that cannot be parsed or validated.
    """
    if not isinstance(text, str):
        raise AuditLogError(f"text must be a string, got {type(text).__name__}")
    return tuple(
        parse_jsonl_line(raw, line_no)
        for line_no, raw in _iter_content_lines(text)
    )


def validate_jsonl(text: str) -> tuple[AuditLogError, ...]:
    """Validate a JSONL document, collecting *every* error rather than raising.

    Returns an empty tuple when the document is fully valid. Each returned
    :class:`AuditLogError` carries the 1-based ``line_no`` it refers to, so a
    caller can report all problems in one pass.

    Beyond per-line schema checks this also verifies the run-level invariant
    that ``seq`` values form the contiguous sequence ``0, 1, 2, ...`` in order;
    a gap or reordering is reported against the offending line.
    """
    if not isinstance(text, str):
        return (
            AuditLogError(f"text must be a string, got {type(text).__name__}"),
        )
    errors: list[AuditLogError] = []
    expected_seq = 0
    for line_no, raw in _iter_content_lines(text):
        try:
            record = parse_jsonl_line(raw, line_no)
        except AuditLogError as exc:
            errors.append(exc)
            expected_seq += 1  # keep positional expectation aligned
            continue
        if record.seq != expected_seq:
            errors.append(
                AuditLogError(
                    f"non-contiguous seq: expected {expected_seq}, "
                    f"got {record.seq}",
                    line_no,
                )
            )
        expected_seq += 1
    return tuple(errors)
