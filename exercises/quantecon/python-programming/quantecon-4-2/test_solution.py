import sys

import numpy as np
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


def test_binomial_rv_exists(sub):
    assert hasattr(sub, "binomial_rv"), "solution must define a function named 'binomial_rv'"
    assert callable(sub.binomial_rv), "'binomial_rv' must be callable"


def test_returns_scalar_integer(sub):
    y = sub.binomial_rv(10, 0.5)
    assert np.ndim(y) == 0, f"binomial_rv must return a scalar, got shape {np.shape(y)}"
    assert float(y).is_integer(), f"binomial_rv must return an integer-valued count, got {y!r}"


def test_in_range_for_many_draws(sub):
    n = 20
    for _ in range(200):
        y = int(sub.binomial_rv(n, 0.3))
        assert 0 <= y <= n, f"draw {y} outside [0, {n}]"


def test_p_zero_always_zero(sub):
    for _ in range(50):
        assert int(sub.binomial_rv(15, 0.0)) == 0, "p=0 must always yield 0 successes"


def test_p_one_always_n(sub):
    for _ in range(50):
        assert int(sub.binomial_rv(15, 1.0)) == 15, "p=1 must always yield n successes"


def test_mean_close_to_np(sub):
    n, p = 50, 0.4
    draws = np.array([int(sub.binomial_rv(n, p)) for _ in range(2000)])
    mean = draws.mean()
    expected = n * p
    # SE of sample mean ≈ sqrt(n*p*(1-p)/N) ≈ sqrt(12/2000) ≈ 0.077
    # Use a generous tolerance to keep the test reliable.
    assert abs(mean - expected) < 0.5, (
        f"sample mean {mean:.3f} not close to expected n*p={expected:.3f} "
        f"— check that each trial succeeds independently with probability p"
    )


def test_variance_close_to_npq(sub):
    n, p = 50, 0.4
    draws = np.array([int(sub.binomial_rv(n, p)) for _ in range(2000)])
    var = draws.var()
    expected = n * p * (1 - p)
    # Catches degenerate implementations (e.g. returning n*p or a single coin flip).
    assert abs(var - expected) < 3.0, (
        f"sample variance {var:.3f} not close to expected n*p*(1-p)={expected:.3f} "
        f"— successes should come from n independent trials, not a single draw"
    )


def test_produces_varied_outputs(sub):
    # Guards against returning a constant like int(n*p).
    draws = {int(sub.binomial_rv(20, 0.5)) for _ in range(100)}
    assert len(draws) > 3, f"binomial_rv produced only {len(draws)} distinct values across 100 draws"
