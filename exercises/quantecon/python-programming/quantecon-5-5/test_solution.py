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


def test_linapprox_exists(sub):
    assert hasattr(sub, "linapprox")
    assert callable(sub.linapprox)


def test_linear_function_exact(sub):
    # A linear function is reproduced exactly by piecewise linear interpolation.
    f = lambda t: 3 * t + 2
    for x in [0.0, 0.25, 0.5, 0.7, 1.0]:
        assert sub.linapprox(f, 0.0, 1.0, 5, x) == pytest.approx(f(x))


def test_endpoints(sub):
    f = lambda t: t * t + 1
    assert sub.linapprox(f, 0.0, 2.0, 5, 0.0) == pytest.approx(f(0.0))
    # x = b may or may not be supported (loop terminates when point > b).
    # Test slightly inside to be safe.
    assert sub.linapprox(f, 0.0, 2.0, 5, 1.999) == pytest.approx(f(1.999), abs=1e-2)


def test_quadratic_close(sub):
    # Piecewise linear is an approximation for nonlinear functions —
    # error decreases as n grows. Use x that is not a grid point at either n.
    f = lambda t: t * t
    err_coarse = abs(sub.linapprox(f, 0.0, 1.0, 3, 0.3) - f(0.3))
    err_fine = abs(sub.linapprox(f, 0.0, 1.0, 101, 0.3) - f(0.3))
    assert err_fine < err_coarse
    assert err_fine < 1e-3


def test_grid_point_exact(sub):
    # At any grid point, the interpolant should match f exactly.
    f = lambda t: 2 ** t
    # 6 grid points on [0, 5] → points at 0, 1, 2, 3, 4, 5.
    for x in [1.0, 2.0, 3.0, 4.0]:
        assert sub.linapprox(f, 0.0, 5.0, 6, x) == pytest.approx(f(x))


def test_no_imports():
    # The problem explicitly says: "without using any imports".
    source = Path(__file__).with_name("submission.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise AssertionError(f"submission must use no imports, found: {ast.unparse(node)}")
