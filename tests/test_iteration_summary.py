from digital_fte.loop import LoopEvent, LoopResult
from digital_fte.iteration_summary import summarize_iterations

def test_summarizes_iterations():
    result=LoopResult("task","completed",2,(),(LoopEvent("planner",1,"a","b"),LoopEvent("validator",1,"b","b"),LoopEvent("planner",2,"b","c")),"c")
    assert summarize_iterations(result) == ((1,2,2,1),(2,1,1,1))

def test_empty_events():
    assert summarize_iterations(LoopResult("t","failed",1,(),(),"x")) == ()
