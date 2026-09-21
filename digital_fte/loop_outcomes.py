"""Deterministic outcome summary for completed and failed agent loops."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from digital_fte.loop import LoopResult

@dataclass(frozen=True)
class LoopOutcomeSummary:
    runs: int
    completed: int
    failed: int
    completion_ratio: float

def summarize_loop_outcomes(results: Iterable[LoopResult]) -> LoopOutcomeSummary:
    items = list(results)
    completed = sum(result.status == "completed" for result in items)
    runs = len(items)
    return LoopOutcomeSummary(runs, completed, runs - completed, round(completed / runs, 4) if runs else 0.0)
