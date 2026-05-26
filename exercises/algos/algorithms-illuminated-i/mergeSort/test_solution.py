import random

import pytest

from submission import merge, merge_sort


# ----- merge_sort -----

def test_empty():
    assert merge_sort([]) == []


def test_single_element():
    assert merge_sort([42]) == [42]


def test_two_elements_unsorted():
    assert merge_sort([2, 1]) == [1, 2]


def test_already_sorted():
    assert merge_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_reverse_sorted():
    assert merge_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


def test_with_duplicates():
    assert merge_sort([3, 1, 2, 1, 3, 2]) == [1, 1, 2, 2, 3, 3]


def test_all_equal():
    assert merge_sort([7, 7, 7, 7]) == [7, 7, 7, 7]


def test_negative_and_mixed():
    assert merge_sort([0, -3, 5, -1, 2, -3]) == [-3, -3, -1, 0, 2, 5]


def test_floats():
    assert merge_sort([1.5, 0.1, 2.2, 1.5, -0.5]) == [-0.5, 0.1, 1.5, 1.5, 2.2]


def test_does_not_mutate_input():
    arr = [4, 2, 5, 1, 3]
    snapshot = list(arr)
    merge_sort(arr)
    assert arr == snapshot


def test_large_random_matches_builtin_sorted():
    rng = random.Random(0xC0FFEE)
    arr = [rng.randint(-1000, 1000) for _ in range(1000)]
    assert merge_sort(arr) == sorted(arr)


def test_odd_length():
    assert merge_sort([3, 1, 4, 1, 5, 9, 2]) == [1, 1, 2, 3, 4, 5, 9]


def test_stable_sort():
    # Tuples with equal first element — stable sort keeps original 2nd-element order.
    data = [(1, "a"), (2, "b"), (1, "c"), (2, "d"), (1, "e")]
    expected = [(1, "a"), (1, "c"), (1, "e"), (2, "b"), (2, "d")]
    assert merge_sort(data) == expected


# ----- merge -----

def test_merge_both_empty():
    assert merge([], []) == []


def test_merge_one_empty():
    assert merge([], [1, 2, 3]) == [1, 2, 3]
    assert merge([1, 2, 3], []) == [1, 2, 3]


def test_merge_interleaved():
    assert merge([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]


def test_merge_disjoint_ranges():
    assert merge([1, 2, 3], [4, 5, 6]) == [1, 2, 3, 4, 5, 6]
    assert merge([4, 5, 6], [1, 2, 3]) == [1, 2, 3, 4, 5, 6]


def test_merge_with_duplicates_across_sides():
    assert merge([1, 2, 2, 4], [2, 3, 5]) == [1, 2, 2, 2, 3, 4, 5]


def test_merge_unequal_lengths():
    assert merge([1], [2, 3, 4, 5]) == [1, 2, 3, 4, 5]
    assert merge([1, 2, 3, 4], [5]) == [1, 2, 3, 4, 5]


def test_merge_does_not_mutate_inputs():
    left = [1, 3, 5]
    right = [2, 4, 6]
    left_snap, right_snap = list(left), list(right)
    merge(left, right)
    assert left == left_snap
    assert right == right_snap


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_merge_random_sorted_halves(seed):
    rng = random.Random(seed)
    left = sorted(rng.randint(-50, 50) for _ in range(rng.randint(0, 30)))
    right = sorted(rng.randint(-50, 50) for _ in range(rng.randint(0, 30)))
    assert merge(left, right) == sorted(left + right)
