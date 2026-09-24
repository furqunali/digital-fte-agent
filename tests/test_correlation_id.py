import pytest

from digital_fte.correlation_id import correlation_id, sequence


def test_returns_hex_of_requested_length():
    cid = correlation_id("run-1", 0)
    assert len(cid) == 16
    assert all(c in "0123456789abcdef" for c in cid)


def test_custom_length():
    assert len(correlation_id("run-1", 0, length=8)) == 8
    assert len(correlation_id("run-1", 0, length=64)) == 64


def test_deterministic():
    assert correlation_id("run-1", 5) == correlation_id("run-1", 5)


def test_different_counter_differs():
    assert correlation_id("run-1", 0) != correlation_id("run-1", 1)


def test_different_seed_differs():
    assert correlation_id("run-1", 0) != correlation_id("run-2", 0)


def test_seed_counter_boundary_unambiguous():
    # ("ab", 1) must not collide with ("a", ... ) style splits.
    assert correlation_id("ab", 1) != correlation_id("a", 1)


def test_counter_zero_allowed():
    assert correlation_id("run", 0)


def test_seed_must_be_string():
    with pytest.raises(TypeError):
        correlation_id(123, 0)


def test_counter_must_be_int():
    with pytest.raises(TypeError):
        correlation_id("run", 1.0)


def test_counter_bool_rejected():
    with pytest.raises(TypeError):
        correlation_id("run", True)


def test_negative_counter_rejected():
    with pytest.raises(ValueError):
        correlation_id("run", -1)


@pytest.mark.parametrize("bad", [0, 3, 65, 100])
def test_length_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        correlation_id("run", 0, length=bad)


def test_length_bool_rejected():
    with pytest.raises(TypeError):
        correlation_id("run", 0, length=True)


def test_sequence_returns_consecutive_ids():
    ids = sequence("run", 3)
    assert ids == (
        correlation_id("run", 0),
        correlation_id("run", 1),
        correlation_id("run", 2),
    )


def test_sequence_with_start_offset():
    ids = sequence("run", 2, start=10)
    assert ids == (correlation_id("run", 10), correlation_id("run", 11))


def test_sequence_zero_count():
    assert sequence("run", 0) == ()


def test_sequence_negative_count_rejected():
    with pytest.raises(ValueError):
        sequence("run", -1)


def test_sequence_ids_are_unique():
    ids = sequence("run", 50)
    assert len(set(ids)) == 50
