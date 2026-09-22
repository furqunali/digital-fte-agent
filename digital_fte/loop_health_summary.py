"""Actionable summaries for Digital FTE orchestration health."""
from __future__ import annotations

from dataclasses import dataclass

from digital_fte.loop_health import LoopHealth


@dataclass(frozen=True)
class LoopHealthSummary:
    status: str
    issues: tuple[str, ...]


def summarize_loop_health(health: LoopHealth) -> LoopHealthSummary:
    """Return stable diagnostics for an orchestration run."""
    issues: list[str] = []
    if health.completed and health.iterations > 1 and health.events == 0:
        issues.append("iterations completed without events")
    if not health.completed:
        issues.append("loop did not complete")
    if health.events and health.state_changes == 0:
        issues.append("no state changes observed")
    if health.agents == 0:
        issues.append("no agents observed")
    return LoopHealthSummary("healthy" if not issues else "attention", tuple(issues))
