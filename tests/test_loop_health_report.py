from digital_fte.loop_outcomes import LoopOutcomeSummary
from digital_fte.loop_health_report import loop_health_report_dict, loop_health_report_json

def test_loop_health_export_is_deterministic():
    result = LoopOutcomeSummary(5, 4, 1, 0.8)
    assert loop_health_report_dict(result) == {
        "runs": 5, "completed": 4, "failed": 1, "completion_ratio": 0.8
    }
    assert loop_health_report_json(result) == '{"completed": 4, "completion_ratio": 0.8, "failed": 1, "runs": 5}'


def test_loop_health_export_rejects_wrong_type():
    try:
        loop_health_report_dict(None)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
