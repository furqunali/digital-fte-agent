"""Deterministic health metrics for an agent orchestration run."""
from __future__ import annotations
from dataclasses import dataclass
from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class LoopHealth:
    iterations: int
    events: int
    agents: int
    state_changes: int
    completed: bool
    unique_states: int

def assess_loop_health(result: LoopResult) -> LoopHealth:
    agents = {event.agent for event in result.events}
    states = {result.final_state}
    states.update(event.input_state for event in result.events)
    states.update(event.output_state for event in result.events)
    changes = sum(event.output_state != event.input_state for event in result.events)
    return LoopHealth(result.iterations, len(result.events), len(agents), changes, result.status == "completed", len(states))
