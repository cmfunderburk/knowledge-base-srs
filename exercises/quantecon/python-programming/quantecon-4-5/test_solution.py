import ast
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sub():
    """Fresh import of submission.py for each test."""
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_x_exists(sub):
    assert hasattr(sub, "x"), "solution must define a function named 'x'"
    assert callable(sub.x), "'x' must be callable"


def test_base_cases(sub):
    assert sub.x(0) == 0
    assert sub.x(1) == 1


def test_first_ten(sub):
    expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    assert [sub.x(i) for i in range(10)] == expected


def test_x_is_recursive():
    # Verify the function calls itself — required by the exercise.
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)
    fn = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "x"),
        None,
    )
    assert fn is not None, "x must be defined as a top-level function"

    found_self_call = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "x":
            found_self_call = True
            break
    assert found_self_call, "x must call itself recursively"
