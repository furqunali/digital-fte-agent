import pytest

from digital_fte.backpressure import (
    APPLY,
    HOLD,
    RELEASE,
    BackpressureController,
    BackpressureDecision,
    evaluate_backpressure,
)


def test_engages_at_high_watermark():
    d = evaluate_backpressure(10, high=10, low=3, engaged=False)
    assert d.engaged is True
    assert d.changed is True
    assert d.action == APPLY


def test_stays_released_below_high():
    d = evaluate_backpressure(9, high=10, low=3, engaged=False)
    assert d.engaged is False
    assert d.changed is False
    assert d.action == HOLD


def test_releases_at_low_watermark():
    d = evaluate_backpressure(3, high=10, low=3, engaged=True)
    assert d.engaged is False
    assert d.changed is True
    assert d.action == RELEASE


def test_stays_engaged_in_hysteresis_band():
    # Between low and high while engaged -> hold engaged.
    d = evaluate_backpressure(5, high=10, low=3, engaged=True)
    assert d.engaged is True
    assert d.changed is False
    assert d.action == HOLD


def test_low_must_be_below_high():
    with pytest.raises(ValueError):
        evaluate_backpressure(5, high=5, low=5, engaged=False)
    with pytest.raises(ValueError):
        evaluate_backpressure(5, high=3, low=5, engaged=False)


def test_negative_depth_rejected():
    with pytest.raises(ValueError):
        evaluate_backpressure(-1, high=10, low=3, engaged=False)


@pytest.mark.parametrize("bad", [True, 1.5, "5"])
def test_bad_depth_type_rejected(bad):
    with pytest.raises(TypeError):
        evaluate_backpressure(bad, high=10, low=3, engaged=False)


def test_engaged_must_be_bool():
    with pytest.raises(TypeError):
        evaluate_backpressure(5, high=10, low=3, engaged=1)


def test_controller_full_cycle():
    ctrl = BackpressureController(high=10, low=3)
    assert ctrl.engaged is False
    assert ctrl.observe(5).action == HOLD  # below high, stays released
    assert ctrl.observe(10).action == APPLY  # engages
    assert ctrl.engaged is True
    assert ctrl.observe(6).action == HOLD  # stays engaged in band
    assert ctrl.observe(3).action == RELEASE  # releases at low
    assert ctrl.engaged is False


def test_controller_can_start_engaged():
    ctrl = BackpressureController(high=10, low=3, engaged=True)
    assert ctrl.engaged is True
    assert ctrl.observe(8).action == HOLD


def test_controller_validates_watermarks():
    with pytest.raises(ValueError):
        BackpressureController(high=3, low=3)


def test_decision_is_dataclass():
    d = evaluate_backpressure(10, high=10, low=3, engaged=False)
    assert isinstance(d, BackpressureDecision)
    assert d.depth == 10
