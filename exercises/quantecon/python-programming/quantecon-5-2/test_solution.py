import ast
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_p_exists(sub):
    assert hasattr(sub, "p"), "solution must define a function named 'p'"
    assert callable(sub.p)


def test_constant_polynomial(sub):
    # p(x) = 5
    assert sub.p(3, [5]) == 5
    assert sub.p(0, [5]) == 5


def test_linear(sub):
    # p(x) = 2 + 4x; p(1) = 6
    assert sub.p(1, (2, 4)) == 6
    assert sub.p(3, (2, 4)) == 14


def test_quadratic(sub):
    # p(x) = 1 + 2x + 3x^2; p(2) = 1 + 4 + 12 = 17
    assert sub.p(2, [1, 2, 3]) == 17


def test_zero_input(sub):
    # p(0) should equal a_0
    assert sub.p(0, [7, 3, 5, 2]) == 7


def test_floats(sub):
    # p(0.5) for coeff (1, 2, 4): 1 + 1 + 1 = 3.0
    assert sub.p(0.5, (1, 2, 4)) == pytest.approx(3.0)


def test_negative_x(sub):
    # p(x) = 1 + x + x^2; p(-2) = 1 - 2 + 4 = 3
    assert sub.p(-2, [1, 1, 1]) == 3


def test_uses_enumerate():
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)
    found = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "enumerate"
        for node in ast.walk(tree)
    )
    assert found, "solution must use enumerate()"
