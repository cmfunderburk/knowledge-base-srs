import sys

import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_count_even_pairs_exists(sub):
    assert hasattr(sub, "count_even_pairs")
    assert callable(sub.count_even_pairs)


def test_textbook_example(sub):
    pairs = ((2, 5), (4, 2), (9, 8), (12, 10))
    assert sub.count_even_pairs(pairs) == 2


def test_empty(sub):
    assert sub.count_even_pairs([]) == 0


def test_all_even(sub):
    assert sub.count_even_pairs([(0, 0), (2, 4), (6, 8)]) == 3


def test_none_even(sub):
    assert sub.count_even_pairs([(1, 3), (5, 7), (9, 11)]) == 0


def test_mixed_with_lists(sub):
    pairs = [(1, 2), (2, 1), (2, 2), (3, 3)]
    assert sub.count_even_pairs(pairs) == 1
