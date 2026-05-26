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


def test_inner_product_exists(sub):
    assert hasattr(sub, "inner_product"), "solution must define 'inner_product'"
    assert callable(sub.inner_product)


def test_simple_case(sub):
    assert sub.inner_product([1, 2, 3], [1, 1, 1]) == 6


def test_tuples_work(sub):
    assert sub.inner_product((1, 2, 3), (4, 5, 6)) == 1 * 4 + 2 * 5 + 3 * 6


def test_empty(sub):
    assert sub.inner_product([], []) == 0


def test_negatives_and_floats(sub):
    assert sub.inner_product([1.5, -2.0], [4.0, 3.0]) == pytest.approx(1.5 * 4.0 + -2.0 * 3.0)


def test_uses_zip():
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)
    found_zip = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "zip"
        for node in ast.walk(tree)
    )
    assert found_zip, "solution must use zip()"
