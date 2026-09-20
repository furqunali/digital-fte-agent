"""Stable JSON contract for multi-agent loop telemetry."""
from __future__ import annotations
from dataclasses import asdict
import json
from digital_fte.loop import LoopResult

def to_json(result: LoopResult) -> str:
    return json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
