from digital_fte.loop_outcomes import summarize_loop_outcomes


def test_summary_rejects_invalid_result_type():
    try:
        summarize_loop_outcomes([object()])
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
