from digital_fte.loop import LoopEvent, LoopResult, LoopStep
from digital_fte.loop_health import assess_loop_health

def test_health_counts_events_agents_and_changes():
    r = LoopResult("task-2","completed",2,(LoopStep("planner","a",1),LoopStep("validator","b",1)),(LoopEvent("planner",1,"start","a"),LoopEvent("validator",1,"a","a"),LoopEvent("planner",2,"a","b")),"b")
    h = assess_loop_health(r)
    assert (h.iterations,h.events,h.agents,h.state_changes,h.completed) == (2,3,2,2,True)

def test_health_marks_failed_result():
    assert not assess_loop_health(LoopResult("task-3","failed",1,(),(),"stuck")).completed
