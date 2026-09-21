"""Deterministic per-agent execution summaries for loop telemetry."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class AgentSummary:
    agent: str
    executions: int
    state_changes: int

def summarize_agents(result: LoopResult) -> tuple[AgentSummary, ...]:
    executions = Counter(event.agent for event in result.events)
    changes = Counter(event.agent for event in result.events if event.output_state != event.input_state)
    return tuple(AgentSummary(agent, executions[agent], changes[agent]) for agent in sorted(executions))
