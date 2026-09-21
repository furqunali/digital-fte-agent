"""Stable JSON export for agent-loop outcome summaries."""
from __future__ import annotations
import json
from dataclasses import asdict
from digital_fte.loop_outcomes import LoopOutcomeSummary

def loop_health_report_dict(result: LoopOutcomeSummary) -> dict:
    if not isinstance(result, LoopOutcomeSummary):
        raise TypeError("result must be a LoopOutcomeSummary")
    return asdict(result)

def loop_health_report_json(result: LoopOutcomeSummary) -> str:
    return json.dumps(loop_health_report_dict(result), sort_keys=True)
