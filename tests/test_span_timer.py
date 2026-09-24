import pytest

from digital_fte.span_timer import Span, SpanRollup, make_span, rollup


def test_make_span_computes_duration():
    span = make_span("stage", 10.0, 13.5)
    assert isinstance(span, Span)
    assert span.name == "stage"
    assert span.start == 10.0
    assert span.end == 13.5
    assert span.duration == 3.5


def test_zero_duration_allowed():
    span = make_span("instant", 5.0, 5.0)
    assert span.duration == 0.0


def test_end_before_start_rejected():
    with pytest.raises(ValueError):
        make_span("bad", 10.0, 9.0)


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        make_span("   ", 0.0, 1.0)


def test_non_string_name_rejected():
    with pytest.raises(TypeError):
        make_span(5, 0.0, 1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_time_rejected(bad):
    with pytest.raises(ValueError):
        make_span("s", 0.0, bad)


def test_bool_time_rejected():
    with pytest.raises(TypeError):
        make_span("s", True, 1.0)


def test_rollup_basic_stats():
    spans = [
        make_span("a", 0.0, 1.0),
        make_span("b", 0.0, 2.0),
        make_span("c", 0.0, 3.0),
    ]
    r = rollup(spans)
    assert isinstance(r, SpanRollup)
    assert r.count == 3
    assert r.total == 6.0
    assert r.average == 2.0
    assert r.minimum == 1.0
    assert r.maximum == 3.0


def test_rollup_single_span():
    r = rollup([make_span("only", 5.0, 9.0)])
    assert r.count == 1
    assert r.total == 4.0
    assert r.average == 4.0
    assert r.minimum == r.maximum == 4.0


def test_rollup_empty_is_all_zero():
    r = rollup([])
    assert r.count == 0
    assert r.total == 0.0
    assert r.average == 0.0
    assert r.minimum == 0.0
    assert r.maximum == 0.0


def test_rollup_rejects_non_span():
    with pytest.raises(TypeError):
        rollup([make_span("a", 0.0, 1.0), "not a span"])


def test_rollup_accepts_generator():
    gen = (make_span(str(i), 0.0, float(i)) for i in range(1, 4))
    r = rollup(gen)
    assert r.count == 3
    assert r.total == 6.0


def test_span_is_frozen():
    from dataclasses import FrozenInstanceError

    span = make_span("s", 0.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        span.duration = 99.0  # type: ignore[misc]


def test_integer_times_accepted():
    span = make_span("s", 1, 4)
    assert span.duration == 3.0
