from digital_fte.agent_summary import summarize_agents
from digital_fte.loop import LoopEvent, LoopResult, LoopStep


def test_summary_is_sorted_and_counts_executions():
    result = LoopResult(
        "task-1", "completed", 1,
        (LoopStep("planner", "a", 1), LoopStep("validator", "b", 1)),
        (LoopEvent("validator", 1, "a", "b"), LoopEvent("planner", 1, "start", "a")),
        "b",
    )
    summary = summarize_agents(result)
    assert [(item.agent, item.executions, item.state_changes) for item in summary] == [
        ("planner", 1, 1),
        ("validator", 1, 1),
    ]
