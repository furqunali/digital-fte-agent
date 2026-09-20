"""Domain models used by the agent workflow."""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Task:
    title: str
    priority: int = 3
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("task title cannot be empty")
        if not 1 <= self.priority <= 5:
            raise ValueError("priority must be between 1 and 5")
