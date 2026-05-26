import sys

import pytest


@pytest.fixture
def sub():
    """Fresh import of submission.py for each test."""
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_factorial_exists(sub):
    assert hasattr(sub, "factorial"), "solution must define a function named 'factorial'"
    assert callable(sub.factorial), "'factorial' must be callable"


def test_factorial_one(sub):
    assert sub.factorial(1) == 1


def test_factorial_small(sub):
    assert sub.factorial(2) == 2
    assert sub.factorial(3) == 6
    assert sub.factorial(4) == 24
    assert sub.factorial(5) == 120


def test_factorial_ten(sub):
    assert sub.factorial(10) == 3628800


def test_factorial_matches_math(sub):
    import math
    for n in range(1, 13):
        assert sub.factorial(n) == math.factorial(n), f"mismatch at n={n}"
