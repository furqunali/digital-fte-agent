from digital_fte.agent_transitions import agent_transitions, transition_count
from digital_fte.loop import LoopEvent, LoopResult

def test_agent_transitions_counts_adjacent_agents():
    result = LoopResult("task","completed",1,(),(
        LoopEvent("planner",1,"start","a"), LoopEvent("validator",1,"a","b"), LoopEvent("planner",1,"b","c")
    ),"c")
    assert agent_transitions(result) == ((("planner","validator"),1),(("validator","planner"),1))
    assert transition_count(result) == 2

def test_agent_transitions_handles_empty_result():
    result = LoopResult("task","failed",0,(),(),"start")
    assert agent_transitions(result) == ()
    assert transition_count(result) == 0
