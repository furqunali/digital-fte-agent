import pytest

from digital_fte.fanout_merge import FanoutMerge, merge_fanout


def test_merges_and_dedupes_by_key():
    lists = [
        [{"id": 1, "src": "a"}, {"id": 2, "src": "a"}],
        [{"id": 2, "src": "b"}, {"id": 3, "src": "b"}],
    ]
    result = merge_fanout(lists, key=lambda x: x["id"])
    assert isinstance(result, FanoutMerge)
    assert [x["id"] for x in result.merged] == [1, 2, 3]
    assert result.dropped == 1


def test_keeps_first_occurrence():
    lists = [
        [{"id": 1, "src": "first"}],
        [{"id": 1, "src": "second"}],
    ]
    result = merge_fanout(lists, key=lambda x: x["id"])
    assert result.merged[0]["src"] == "first"
    assert result.dropped == 1


def test_preserves_order():
    lists = [[3, 1], [2, 3], [4, 1]]
    result = merge_fanout(lists, key=lambda x: x)
    assert result.merged == (3, 1, 2, 4)


def test_no_duplicates():
    lists = [[1, 2], [3, 4]]
    result = merge_fanout(lists, key=lambda x: x)
    assert result.merged == (1, 2, 3, 4)
    assert result.dropped == 0


def test_empty_lists():
    result = merge_fanout([], key=lambda x: x)
    assert result.merged == ()
    assert result.dropped == 0


def test_empty_groups():
    result = merge_fanout([[], [], []], key=lambda x: x)
    assert result.merged == ()


def test_keys_reported():
    lists = [["apple", "avocado"], ["banana"]]
    result = merge_fanout(lists, key=lambda s: s[0])
    assert result.merged == ("apple", "banana")
    assert result.keys == ("a", "b")


def test_key_must_be_callable():
    with pytest.raises(TypeError):
        merge_fanout([[1]], key="not callable")  # type: ignore[arg-type]


def test_result_lists_must_be_iterable():
    with pytest.raises(TypeError):
        merge_fanout(123, key=lambda x: x)  # type: ignore[arg-type]


def test_string_result_lists_rejected():
    with pytest.raises(TypeError):
        merge_fanout("abc", key=lambda x: x)


def test_group_must_be_iterable():
    with pytest.raises(TypeError):
        merge_fanout([123], key=lambda x: x)


def test_unhashable_key_rejected():
    with pytest.raises(TypeError):
        merge_fanout([[1]], key=lambda x: [x])  # list key is unhashable


def test_accepts_generator_of_groups():
    def groups():
        yield [1, 2]
        yield [2, 3]

    result = merge_fanout(groups(), key=lambda x: x)
    assert result.merged == (1, 2, 3)
    assert result.dropped == 1
