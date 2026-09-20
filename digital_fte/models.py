from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Task:
    source: Path
    task_id: str
    title: str
    body: str

@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str
    output: Path
    log: Path
    started_at: str
    finished_at: str
    error: str | None = None
