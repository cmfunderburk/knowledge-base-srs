import sys
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")  # must come before any pyplot import

import numpy as np
import pytest


@pytest.fixture
def sub():
    """Fresh import of submission.py for each test, with plt.show() mocked."""
    sys.modules.pop("submission", None)
    with patch("matplotlib.pyplot.show"):
        import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_runs_without_error(sub):
    pass


def test_x_exists_and_has_correct_length(sub):
    assert hasattr(sub, "x"), "solution must create a variable named 'x'"
    assert len(sub.x) == 201  # T=200 → T+1 elements


def test_initial_condition(sub):
    assert sub.x[0] == 0


def test_ar1_dynamics(sub):
    x = np.asarray(sub.x)
    assert x[1:].std() > 0.1, "series should have non-trivial variance"
    lag1 = np.corrcoef(x[:-1], x[1:])[0, 1]
    assert lag1 > 0.7, f"lag-1 autocorrelation {lag1:.3f} too low for α ≈ 0.9"
