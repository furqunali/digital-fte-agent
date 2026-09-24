import pytest

from digital_fte.stale_reaper import StaleItem, find_stale, stale_keys


def test_find_stale_from_mapping():
    tasks = {"a": 0.0, "b": 90.0, "c": 50.0}
    stale = find_stale(tasks, now=100.0, max_age=30.0)
    # a: age 100 (stale), b: age 10 (fresh), c: age 50 (stale)
    keys = [s.key for s in stale]
    assert keys == ["a", "c"]  # oldest first


def test_find_stale_from_pairs():
    tasks = [("a", 0.0), ("b", 95.0)]
    stale = find_stale(tasks, now=100.0, max_age=30.0)
    assert [s.key for s in stale] == ["a"]


def test_returns_stale_item_records():
    stale = find_stale({"a": 10.0}, now=100.0, max_age=30.0)
    assert isinstance(stale[0], StaleItem)
    assert stale[0].last_update == 10.0
    assert stale[0].age == 90.0


def test_threshold_is_strict():
    # age exactly equal to max_age is NOT stale
    assert find_stale({"a": 70.0}, now=100.0, max_age=30.0) == ()
    # one unit older is stale
    assert len(find_stale({"a": 69.0}, now=100.0, max_age=30.0)) == 1


def test_nothing_stale_returns_empty():
    assert find_stale({"a": 99.0, "b": 100.0}, now=100.0, max_age=30.0) == ()


def test_sorted_oldest_first():
    tasks = {"recent": 60.0, "ancient": 0.0, "mid": 30.0}
    stale = find_stale(tasks, now=100.0, max_age=10.0)
    assert [s.key for s in stale] == ["ancient", "mid", "recent"]


def test_stable_order_on_equal_age():
    tasks = [("a", 0.0), ("b", 0.0), ("c", 0.0)]
    stale = find_stale(tasks, now=100.0, max_age=10.0)
    assert [s.key for s in stale] == ["a", "b", "c"]


def test_stale_keys_helper():
    tasks = {"a": 0.0, "b": 99.0}
    assert stale_keys(tasks, now=100.0, max_age=30.0) == ("a",)


def test_max_age_zero_flags_all_past():
    tasks = {"a": 99.0, "b": 100.0}
    # age 1 > 0 stale; age 0 not > 0
    assert stale_keys(tasks, now=100.0, max_age=0.0) == ("a",)


def test_empty_input():
    assert find_stale({}, now=100.0, max_age=30.0) == ()
    assert find_stale([], now=100.0, max_age=30.0) == ()


def test_bad_items_type_rejected():
    with pytest.raises(TypeError):
        find_stale("not-items", now=100.0, max_age=30.0)


def test_bad_pair_shape_rejected():
    with pytest.raises(TypeError):
        find_stale([("a", 1.0, "extra")], now=100.0, max_age=30.0)


def test_negative_max_age_rejected():
    with pytest.raises(ValueError):
        find_stale({"a": 0.0}, now=100.0, max_age=-1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_now_rejected(bad):
    with pytest.raises(ValueError):
        find_stale({"a": 0.0}, now=bad, max_age=30.0)


def test_now_bool_rejected():
    with pytest.raises(TypeError):
        find_stale({"a": 0.0}, now=True, max_age=30.0)


def test_bad_last_update_rejected():
    with pytest.raises(TypeError):
        find_stale({"a": "yesterday"}, now=100.0, max_age=30.0)
