import math
import sys

import pytest


@pytest.fixture
def sub():
    """Fresh import of submission.py for each test."""
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_runs_without_error(sub):
    pass


def test_pi_estimate_exists(sub):
    assert hasattr(sub, "pi_estimate"), "solution must create a variable named 'pi_estimate'"


def test_pi_estimate_is_finite_number(sub):
    assert math.isfinite(float(sub.pi_estimate)), "pi_estimate must be a finite number"


def test_pi_estimate_close_to_pi(sub):
    err = abs(float(sub.pi_estimate) - math.pi)
    assert err < 0.1, (
        f"pi_estimate={float(sub.pi_estimate):.4f} not within 0.1 of π "
        f"(error={err:.4f}) — check Monte Carlo logic or increase n"
    )
