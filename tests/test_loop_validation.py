from digital_fte.loop import LoopEvent, LoopResult, LoopStep
from digital_fte.loop_validation import is_valid_loop_result, validate_loop_result


def test_valid_loop_result():
    r=LoopResult("t","completed",1,(LoopStep("planner","x",1),),(LoopEvent("planner",1,"a","x"),),"x")
    assert is_valid_loop_result(r)
def test_invalid_event_is_reported():
    r=LoopResult("t","completed",1,(),(LoopEvent("",0,"a","b"),),"b")
    assert "event agent is empty" in validate_loop_result(r) and not is_valid_loop_result(r)
