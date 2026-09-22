"""Deterministic audit metrics for multi-agent loop results."""
from __future__ import annotations
from dataclasses import dataclass
from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class LoopAudit:
    iterations: int
    steps: int
    events: int
    status: str
    agents: tuple[str, ...]

def audit_loop(result: LoopResult) -> LoopAudit:
    agents = tuple(dict.fromkeys(step.agent for step in result.steps))
    return LoopAudit(
        iterations=result.iterations,
        steps=len(result.steps),
        events=len(result.events),
        status=result.status,
        agents=agents,
    )
