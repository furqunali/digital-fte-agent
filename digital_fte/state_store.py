"""Deterministic JSON state persistence for multi-agent loops."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from digital_fte.loop import LoopResult


class LoopStateStore:
    """Persist and restore the latest loop result for a task."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, result: LoopResult) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{result.task_id}.json"
        path.write_text(
            json.dumps(asdict(result), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return path

    def load(self, task_id: str) -> LoopResult:
        data = json.loads((self.root / f"{task_id}.json").read_text(encoding="utf-8"))
        return LoopResult(
            task_id=data["task_id"],
            status=data["status"],
            iterations=data["iterations"],
            steps=tuple(
                {"agent": step["agent"], "state": step["state"], "iteration": step["iteration"]}
                for step in data["steps"]
            ),
            events=tuple(
                {
                    "agent": event["agent"],
                    "iteration": event["iteration"],
                    "input_state": event["input_state"],
                    "output_state": event["output_state"],
                }
                for event in data["events"]
            ),
            final_state=data["final_state"],
        )
