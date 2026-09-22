"""Ordered, typed run timeline derived from an agent loop result.

Where :mod:`digital_fte.loop` records raw agent transitions, this module lifts a
:class:`~digital_fte.loop.LoopResult` into a chronological *timeline* of typed
events that narrate the run: when it started, when each iteration opened and
closed, what each agent did, and how the run terminated. The timeline is a pure
deterministic projection of the result -- no clocks, no I/O -- so it is safe to
persist, diff, or render.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from digital_fte.loop import LoopResult

RUN_STARTED = "run_started"
ITERATION_STARTED = "iteration_started"
AGENT_ACTED = "agent_acted"
ITERATION_COMPLETED = "iteration_completed"
RUN_COMPLETED = "run_completed"
RUN_FAILED = "run_failed"

#: Every event kind the timeline may emit, in no particular order.
TIMELINE_KINDS: frozenset[str] = frozenset(
    {
        RUN_STARTED,
        ITERATION_STARTED,
        AGENT_ACTED,
        ITERATION_COMPLETED,
        RUN_COMPLETED,
        RUN_FAILED,
    }
)

_TERMINAL_KINDS: frozenset[str] = frozenset({RUN_COMPLETED, RUN_FAILED})


@dataclass(frozen=True)
class TimelineEvent:
    """A single ordered, typed entry in a run timeline.

    Attributes:
        sequence: Zero-based position in the timeline; strictly increasing.
        iteration: Loop iteration the event belongs to (``0`` for the opening
            ``run_started`` marker of an empty run).
        kind: One of :data:`TIMELINE_KINDS`.
        agent: Acting agent name for ``agent_acted`` events, otherwise ``None``.
        from_state: State observed before an ``agent_acted`` event, else ``None``.
        to_state: State produced by an ``agent_acted`` event, else ``None``.
        changed: ``True`` when an ``agent_acted`` event altered the state.
    """

    sequence: int
    iteration: int
    kind: str
    agent: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    changed: bool = field(default=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise TypeError("sequence must be an integer")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.iteration, int) or isinstance(self.iteration, bool):
            raise TypeError("iteration must be an integer")
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.kind not in TIMELINE_KINDS:
            raise ValueError(f"unknown timeline kind: {self.kind!r}")
        if self.kind == AGENT_ACTED:
            if self.agent is None:
                raise ValueError("agent_acted events require an agent")
            if self.changed != (self.from_state != self.to_state):
                raise ValueError("changed must reflect from_state != to_state")
        elif self.agent is not None:
            raise ValueError(f"{self.kind} events must not name an agent")

    @property
    def is_terminal(self) -> bool:
        """Whether this event closes the run."""
        return self.kind in _TERMINAL_KINDS


def _first_iteration(result: LoopResult) -> int:
    """Iteration to attribute the opening/terminal markers of an empty run to."""
    return result.events[0].iteration if result.events else 0


def build_timeline(result: LoopResult) -> tuple[TimelineEvent, ...]:
    """Project a :class:`LoopResult` into an ordered tuple of typed events.

    The timeline always opens with a ``run_started`` marker and closes with a
    single terminal ``run_completed`` or ``run_failed`` event matching
    ``result.status``. Between them, each loop iteration contributes an
    ``iteration_started`` marker, one ``agent_acted`` event per recorded agent
    transition (in execution order), and an ``iteration_completed`` marker.

    A run with no recorded events still yields ``run_started`` followed by the
    terminal event, so the timeline is never empty.

    Args:
        result: The completed or failed loop result to project.

    Returns:
        A tuple of :class:`TimelineEvent` with contiguous ``sequence`` values.

    Raises:
        TypeError: If ``result`` is not a :class:`LoopResult`.
        ValueError: If ``result.status`` is not ``"completed"`` or ``"failed"``.
    """
    if not isinstance(result, LoopResult):
        raise TypeError("result must be a LoopResult")
    if result.status not in ("completed", "failed"):
        raise ValueError(f"unsupported loop status: {result.status!r}")

    events = result.events
    initial_state = events[0].input_state if events else result.final_state

    timeline: list[TimelineEvent] = []
    seq = 0

    timeline.append(
        TimelineEvent(seq, _first_iteration(result), RUN_STARTED, to_state=initial_state)
    )
    seq += 1

    open_iteration: int | None = None
    for event in events:
        if open_iteration != event.iteration:
            if open_iteration is not None:
                timeline.append(
                    TimelineEvent(seq, open_iteration, ITERATION_COMPLETED)
                )
                seq += 1
            timeline.append(TimelineEvent(seq, event.iteration, ITERATION_STARTED))
            seq += 1
            open_iteration = event.iteration
        timeline.append(
            TimelineEvent(
                seq,
                event.iteration,
                AGENT_ACTED,
                agent=event.agent,
                from_state=event.input_state,
                to_state=event.output_state,
                changed=event.input_state != event.output_state,
            )
        )
        seq += 1

    if open_iteration is not None:
        timeline.append(TimelineEvent(seq, open_iteration, ITERATION_COMPLETED))
        seq += 1

    terminal_kind = RUN_COMPLETED if result.status == "completed" else RUN_FAILED
    terminal_iteration = open_iteration if open_iteration is not None else _first_iteration(result)
    timeline.append(
        TimelineEvent(seq, terminal_iteration, terminal_kind, to_state=result.final_state)
    )
    return tuple(timeline)


def filter_timeline(
    timeline: tuple[TimelineEvent, ...], kind: str
) -> tuple[TimelineEvent, ...]:
    """Return only the events of a given ``kind``, preserving order.

    Raises:
        ValueError: If ``kind`` is not a recognised timeline kind.
    """
    if kind not in TIMELINE_KINDS:
        raise ValueError(f"unknown timeline kind: {kind!r}")
    return tuple(event for event in timeline if event.kind == kind)


def render_timeline(timeline: tuple[TimelineEvent, ...]) -> tuple[str, ...]:
    """Render a timeline into deterministic, human-readable lines.

    Each line is prefixed with its zero-padded sequence number so lines sort
    lexicographically into execution order.
    """
    width = max((len(str(len(timeline) - 1)), 1)) if timeline else 1
    lines: list[str] = []
    for event in timeline:
        prefix = f"[{event.sequence:0{width}d}] i{event.iteration} {event.kind}"
        if event.kind == AGENT_ACTED:
            arrow = "->" if event.changed else "=="
            lines.append(
                f"{prefix}: {event.agent} {event.from_state} {arrow} {event.to_state}"
            )
        elif event.to_state is not None:
            lines.append(f"{prefix}: {event.to_state}")
        else:
            lines.append(prefix)
    return tuple(lines)
