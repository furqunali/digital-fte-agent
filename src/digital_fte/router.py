"""Deterministic task routing rules."""
from .models import Task


def route_task(task: Task) -> str:
    """Select a workflow queue from task metadata and priority."""
    kind = task.metadata.get("kind", "general").lower()
    if kind in {"finance", "invoice", "payroll"}:
        return "finance"
    if kind in {"sales", "crm", "customer"}:
        return "customer_ops"
    if task.priority <= 2:
        return "priority"
    return "general"
