from digital_fte.loop import LoopResult
from digital_fte.loop_outcomes import summarize_loop_outcomes


def r(status):
    return LoopResult("t", status, 1, (), (), "s")

def test_outcome_ratio():
    result = summarize_loop_outcomes([r("completed"), r("failed"), r("completed")])
    assert result.runs == 3 and result.completed == 2 and result.failed == 1
    assert result.completion_ratio == round(2/3, 4)

def test_empty_outcomes():
    assert summarize_loop_outcomes([]).completion_ratio == 0.0
