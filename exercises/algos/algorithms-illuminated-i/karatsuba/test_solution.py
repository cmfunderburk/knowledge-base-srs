import ast
import random
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_karatsuba_exists(sub):
    assert hasattr(sub, "karatsuba")
    assert callable(sub.karatsuba)


def test_single_digits(sub):
    for x in range(10):
        for y in range(10):
            assert sub.karatsuba(x, y) == x * y


def test_zero_cases(sub):
    assert sub.karatsuba(0, 12345) == 0
    assert sub.karatsuba(12345, 0) == 0
    assert sub.karatsuba(0, 0) == 0


def test_two_digit_pairs(sub):
    for x in [10, 23, 99]:
        for y in [11, 47, 88]:
            assert sub.karatsuba(x, y) == x * y


def test_textbook_size(sub):
    # 4-digit × 4-digit — exercises the recursion properly.
    assert sub.karatsuba(1234, 5678) == 1234 * 5678
    assert sub.karatsuba(5678, 1234) == 5678 * 1234


def test_uneven_lengths(sub):
    assert sub.karatsuba(3, 14159) == 3 * 14159
    assert sub.karatsuba(14159, 3) == 14159 * 3
    assert sub.karatsuba(12, 345678) == 12 * 345678


def test_classic_example(sub):
    # The example from Algorithms Illuminated.
    assert sub.karatsuba(3141592653589793, 2718281828459045) == 3141592653589793 * 2718281828459045


def test_large_random(sub):
    rng = random.Random(0xC0DE)
    for _ in range(20):
        x = rng.randrange(10 ** 20)
        y = rng.randrange(10 ** 20)
        assert sub.karatsuba(x, y) == x * y


def test_does_not_just_call_builtin_multiply():
    """The submission must implement the recursive algorithm, not just `x * y`.

    We allow `*` (you need it at the base case and in the combine step), but
    we require that `karatsuba` calls itself — the whole point of the exercise.
    """
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)

    fn = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "karatsuba"),
        None,
    )
    assert fn is not None, "karatsuba must be defined as a top-level function"

    self_call = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "karatsuba"
        for n in ast.walk(fn)
    )
    assert self_call, "karatsuba must call itself recursively"
