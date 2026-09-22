from digital_fte.loop import LoopResult
from digital_fte.loop_health import assess_loop_health
from digital_fte.loop_health_summary import summarize_loop_health


def test_summary_marks_completed_run_healthy():
    result = LoopResult("task", "completed", 1, (), (), "done")
    health = assess_loop_health(result)
    summary = summarize_loop_health(health)
    assert summary.status == "healthy"
    assert summary.issues == ()


def test_summary_reports_failed_run():
    result = LoopResult("task", "failed", 1, (), (), "stuck")
    summary = summarize_loop_health(assess_loop_health(result))
    assert summary.status == "attention"
    assert summary.issues == ("loop did not complete", "no agents observed")


def test_summary_reports_iterations_without_events():
    result = LoopResult("task", "completed", 2, (), (), "done")
    summary = summarize_loop_health(assess_loop_health(result))
    assert summary.status == "attention"
    assert summary.issues == ("iterations completed without events", "no agents observed")
