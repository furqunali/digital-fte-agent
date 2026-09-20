import pytest

from src.digital_fte.models import Task
from src.digital_fte.router import route_task


def test_routes_finance_tasks():
    assert route_task(Task("Review invoice", metadata={"kind": "invoice"})) == "finance"


def test_routes_customer_tasks():
    assert route_task(Task("Update CRM", metadata={"kind": "crm"})) == "customer_ops"


def test_routes_high_priority_tasks():
    assert route_task(Task("Urgent request", priority=1)) == "priority"


def test_rejects_invalid_priority():
    with pytest.raises(ValueError):
        Task("Bad priority", priority=9)
