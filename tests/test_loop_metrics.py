import pytest

from digital_fte.loop import LoopEvent, LoopResult
from digital_fte.loop_metrics import aggregate_loop_metrics


def make_result(status, iterations, events=()):
    return LoopResult("task", status, iterations, (), tuple(events), "final")


def events_for(iterations, per_iteration):
    return tuple(
        LoopEvent("agent", i, "a", "b")
        for i in range(1, iterations + 1)
        for _ in range(per_iteration)
    )


def test_empty_input_is_all_zero():
    metrics = aggregate_loop_metrics([])
    assert metrics.runs == 0
    assert metrics.successes == 0
    assert metrics.failures == 0
    assert metrics.success_rate == 0.0
    assert metrics.total_iterations == 0
    assert metrics.avg_iterations == 0.0
    assert metrics.avg_iterations_to_success == 0.0
    assert metrics.total_events == 0
    assert metrics.throughput == 0.0


def test_success_rate_and_counts():
    metrics = aggregate_loop_metrics(
        [
            make_result("completed", 1),
            make_result("failed", 3),
            make_result("completed", 2),
        ]
    )
    assert metrics.runs == 3
    assert metrics.successes == 2
    assert metrics.failures == 1
    assert metrics.success_rate == round(2 / 3, 4)


def test_avg_iterations_all_runs_vs_success_only():
    metrics = aggregate_loop_metrics(
        [
            make_result("completed", 2),
            make_result("failed", 6),
        ]
    )
    assert metrics.total_iterations == 8
    assert metrics.avg_iterations == 4.0
    # Only the completed run's iterations feed the success-only average.
    assert metrics.avg_iterations_to_success == 2.0


def test_throughput_is_events_per_iteration():
    metrics = aggregate_loop_metrics(
        [
            make_result("completed", 2, events_for(2, 3)),  # 6 events / 2 iters
            make_result("completed", 1, events_for(1, 2)),  # 2 events / 1 iter
        ]
    )
    assert metrics.total_events == 8
    assert metrics.total_iterations == 3
    assert metrics.throughput == round(8 / 3, 4)


def test_no_success_leaves_success_average_zero():
    metrics = aggregate_loop_metrics([make_result("failed", 3), make_result("failed", 5)])
    assert metrics.successes == 0
    assert metrics.avg_iterations_to_success == 0.0
    assert metrics.success_rate == 0.0


def test_zero_iterations_does_not_divide_by_zero():
    metrics = aggregate_loop_metrics([make_result("failed", 0)])
    assert metrics.total_iterations == 0
    assert metrics.avg_iterations == 0.0
    assert metrics.throughput == 0.0


def test_accepts_any_iterable_generator():
    metrics = aggregate_loop_metrics(
        make_result("completed", 1) for _ in range(4)
    )
    assert metrics.runs == 4
    assert metrics.success_rate == 1.0


def test_rejects_non_loopresult():
    with pytest.raises(TypeError):
        aggregate_loop_metrics([make_result("completed", 1), "not-a-result"])


def test_rejects_negative_iterations():
    with pytest.raises(ValueError):
        aggregate_loop_metrics([make_result("completed", -1)])


def test_metrics_is_frozen():
    metrics = aggregate_loop_metrics([make_result("completed", 1)])
    with pytest.raises((AttributeError, TypeError)):
        metrics.runs = 99  # type: ignore[misc]
