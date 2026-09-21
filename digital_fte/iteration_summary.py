"""Deterministic per-iteration execution summaries for loop telemetry."""
from __future__ import annotations
from dataclasses import dataclass
from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class IterationSummary:
    iteration: int
    events: int
    agents: int
    state_changes: int

def summarize_iterations(result: LoopResult) -> tuple[IterationSummary, ...]:
    groups: dict[int,list] = {}
    for event in result.events:
        groups.setdefault(event.iteration,[]).append(event)
    return tuple(IterationSummary(i,len(events),len({e.agent for e in events}),
        sum(e.input_state != e.output_state for e in events))
        for i,events in sorted(groups.items()))
