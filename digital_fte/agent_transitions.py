"""Deterministic agent-to-agent transition metrics."""
from __future__ import annotations

from collections import Counter

from digital_fte.loop import LoopResult


def agent_transitions(result: LoopResult) -> tuple[tuple[str, str], ...]:
    agents = [event.agent for event in result.events]
    return tuple(sorted(Counter(zip(agents, agents[1:])).items()))

def transition_count(result: LoopResult) -> int:
    return max(len(result.events) - 1, 0)
