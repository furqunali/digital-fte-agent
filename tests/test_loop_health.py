from digital_fte.loop import LoopEvent, LoopResult, LoopStep
from digital_fte.loop_health import assess_loop_health


def test_health_counts_events_agents_changes_and_states():
    r = LoopResult("task-2","completed",2,(LoopStep("planner","a",1),LoopStep("validator","b",1)),(LoopEvent("planner",1,"start","a"),LoopEvent("validator",1,"a","a"),LoopEvent("planner",2,"a","b")),"b")
    h = assess_loop_health(r)
    assert (h.iterations,h.events,h.agents,h.state_changes,h.completed,h.unique_states) == (2,3,2,2,True,3)

def test_health_marks_failed_result():
    h = assess_loop_health(LoopResult("task-3","failed",1,(),(), "stuck"))
    assert not h.completed
    assert h.unique_states == 1
