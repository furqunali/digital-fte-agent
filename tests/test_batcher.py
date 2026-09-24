import pytest

from digital_fte.batcher import batch


def test_batch_by_count():
    result = batch([1, 2, 3, 4, 5], max_count=2)
    assert result == ((1, 2), (3, 4), (5,))


def test_exact_multiple_by_count():
    result = batch([1, 2, 3, 4], max_count=2)
    assert result == ((1, 2), (3, 4))


def test_single_batch_when_under_count():
    result = batch([1, 2], max_count=10)
    assert result == ((1, 2),)


def test_batch_by_size_using_len():
    # each string's len contributes to cumulative size
    result = batch(["ab", "cd", "e"], max_size=3)
    # "ab"(2) + "cd"(2) = 4 > 3 -> split; "ab" alone, then "cd"+"e"=3
    assert result == (("ab",), ("cd", "e"))


def test_batch_by_size_custom_size_of():
    items = [{"n": 3}, {"n": 3}, {"n": 5}]
    result = batch(items, max_size=6, size_of=lambda d: d["n"])
    assert result == (({"n": 3}, {"n": 3}), ({"n": 5},))


def test_oversized_item_emitted_alone():
    result = batch(["x", "toolong", "y"], max_size=3, size_of=len)
    assert result == (("x",), ("toolong",), ("y",))


def test_count_and_size_both_applied():
    # max_count=3 but size forces earlier split
    result = batch([2, 2, 2, 2], max_count=3, max_size=4, size_of=lambda n: n)
    assert result == ((2, 2), (2, 2))


def test_empty_input_returns_empty():
    assert batch([], max_count=3) == ()


def test_preserves_order():
    result = batch(range(6), max_count=2)
    assert result == ((0, 1), (2, 3), (4, 5))


def test_accepts_generator():
    result = batch((i for i in range(5)), max_count=2)
    assert result == ((0, 1), (2, 3), (4,))


def test_requires_at_least_one_limit():
    with pytest.raises(ValueError):
        batch([1, 2, 3])


def test_max_count_must_be_positive():
    with pytest.raises(ValueError):
        batch([1], max_count=0)


def test_max_count_bool_rejected():
    with pytest.raises(TypeError):
        batch([1], max_count=True)


def test_max_size_must_be_positive():
    with pytest.raises(ValueError):
        batch([1], max_size=0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_max_size_must_be_finite(bad):
    with pytest.raises(ValueError):
        batch([1], max_size=bad)


def test_size_of_must_be_callable():
    with pytest.raises(TypeError):
        batch([1], max_size=5, size_of="notcallable")


def test_size_of_non_number_rejected():
    with pytest.raises(TypeError):
        batch([1], max_size=5, size_of=lambda x: "big")


def test_size_of_negative_rejected():
    with pytest.raises(ValueError):
        batch([1], max_size=5, size_of=lambda x: -1)


def test_zero_size_items_group_under_count_only():
    # zero-size items never trip max_size, so only count limits them
    result = batch([0, 0, 0], max_count=2, max_size=10, size_of=lambda x: 0)
    assert result == ((0, 0), (0,))
