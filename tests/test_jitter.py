import pytest

from digital_fte.jitter import clamped_jitter, equal_jitter, full_jitter


# --- full jitter ------------------------------------------------------------

def test_full_jitter_zero_fraction():
    assert full_jitter(10.0, 0.0) == 0.0


def test_full_jitter_one_fraction():
    assert full_jitter(10.0, 1.0) == 10.0


def test_full_jitter_half_fraction():
    assert full_jitter(10.0, 0.5) == 5.0


def test_full_jitter_deterministic():
    assert full_jitter(8.0, 0.25) == full_jitter(8.0, 0.25) == 2.0


# --- equal jitter -----------------------------------------------------------

def test_equal_jitter_zero_fraction_is_half():
    assert equal_jitter(10.0, 0.0) == 5.0


def test_equal_jitter_one_fraction_is_full():
    assert equal_jitter(10.0, 1.0) == 10.0


def test_equal_jitter_half_fraction():
    assert equal_jitter(10.0, 0.5) == pytest.approx(7.5)


def test_equal_jitter_bounds():
    for frac in (0.0, 0.3, 0.7, 1.0):
        value = equal_jitter(20.0, frac)
        assert 10.0 <= value <= 20.0


# --- clamped jitter ---------------------------------------------------------

def test_clamped_jitter_applies_floor():
    assert clamped_jitter(10.0, 0.0, floor=2.0) == 2.0


def test_clamped_jitter_applies_ceiling():
    assert clamped_jitter(10.0, 1.0, ceiling=6.0) == 6.0


def test_clamped_jitter_within_bounds_untouched():
    assert clamped_jitter(10.0, 0.5, floor=1.0, ceiling=9.0) == 5.0


def test_clamped_jitter_floor_exceeds_ceiling_rejected():
    with pytest.raises(ValueError):
        clamped_jitter(10.0, 0.5, floor=8.0, ceiling=2.0)


# --- validation -------------------------------------------------------------

@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan")])
def test_fraction_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        full_jitter(10.0, bad)


def test_negative_delay_rejected():
    with pytest.raises(ValueError):
        full_jitter(-1.0, 0.5)


@pytest.mark.parametrize("bad", [float("inf"), float("nan")])
def test_non_finite_delay_rejected(bad):
    with pytest.raises(ValueError):
        equal_jitter(bad, 0.5)


def test_bool_fraction_rejected():
    with pytest.raises(TypeError):
        full_jitter(10.0, True)


def test_string_delay_rejected():
    with pytest.raises(TypeError):
        full_jitter("10", 0.5)
