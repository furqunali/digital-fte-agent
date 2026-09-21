"""Deterministic per-agent execution summaries for loop telemetry."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class AgentSummary:
    agent: str
    executions: int
    failed_outputs: int

def summarize_agents(result: LoopResult) -> tuple[AgentSummary, ...]:
    executions = Counter(event.agent for event in result.events)
    failures = Counter(
        event.agent for event in result.events
        if event.output_state != event.input_state and result.status == "failed"
    )
    return tuple(
        AgentSummary(agent, executions[agent], failures[agent])
        for agent in sorted(executions)
    )
