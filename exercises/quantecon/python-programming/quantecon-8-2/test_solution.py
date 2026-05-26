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


def test_polynomial_exists(sub):
    assert hasattr(sub, "Polynomial"), "solution must define a class named 'Polynomial'"


def test_stores_coefficients(sub):
    p = sub.Polynomial([1, 2, 3])
    assert hasattr(p, "coefficients")
    assert list(p.coefficients) == [1, 2, 3]


def test_call_evaluates(sub):
    # p(x) = 2 + 4x; p(1) = 6, p(3) = 14
    p = sub.Polynomial([2, 4])
    assert p(1) == 6
    assert p(3) == 14


def test_call_quadratic(sub):
    # p(x) = 1 + 2x + 3x^2; p(2) = 1 + 4 + 12 = 17
    p = sub.Polynomial([1, 2, 3])
    assert p(2) == 17


def test_differentiate_returns_new_coeffs(sub):
    # p(x) = 1 + 2x + 3x^2 → p'(x) = 2 + 6x
    p = sub.Polynomial([1, 2, 3])
    new = p.differentiate()
    assert list(new) == [2, 6]


def test_differentiate_mutates_self(sub):
    p = sub.Polynomial([1, 2, 3])
    p.differentiate()
    assert list(p.coefficients) == [2, 6]


def test_differentiate_then_evaluate(sub):
    # p(x) = 1 + 2x + 3x^2; p'(x) = 2 + 6x; p'(1) = 8
    p = sub.Polynomial([1, 2, 3])
    p.differentiate()
    assert p(1) == 8


def test_differentiate_twice(sub):
    # p(x) = x^3 → p' = 3x^2 → p'' = 6x
    p = sub.Polynomial([0, 0, 0, 1])
    p.differentiate()
    assert list(p.coefficients) == [0, 0, 3]
    p.differentiate()
    assert list(p.coefficients) == [0, 6]


def test_repr_is_defined(sub):
    # Default object.__repr__ returns '<...Polynomial object at 0x...>',
    # which is not useful. The student must override __repr__.
    p = sub.Polynomial([1, 2, 3])
    r = repr(p)
    assert not r.startswith("<"), (
        f"Polynomial must define __repr__; got the default object repr: {r!r}"
    )


def test_repr_roundtrip(sub):
    # Convention: eval(repr(p)) should reconstruct an equivalent Polynomial.
    p = sub.Polynomial([1, 2, 3])
    rebuilt = eval(repr(p), {"Polynomial": sub.Polynomial})
    assert isinstance(rebuilt, sub.Polynomial)
    assert list(rebuilt.coefficients) == [1, 2, 3]


def test_no_imports():
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise AssertionError(f"submission must use no imports, found: {ast.unparse(node)}")
