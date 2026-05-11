import numpy as np
import pytest
from submission import simulate


def test_length():
    rng = np.random.default_rng(42)
    x = simulate(0.9, 200, rng)
    assert len(x) == 201


def test_initial_condition():
    rng = np.random.default_rng(42)
    x = simulate(0.9, 200, rng)
    assert x[0] == 0.0


def test_returns_ndarray():
    rng = np.random.default_rng(42)
    x = simulate(0.9, 10, rng)
    assert isinstance(x, np.ndarray)


def test_deterministic_with_seed():
    rng = np.random.default_rng(0)
    x = simulate(0.9, 5, rng)

    rng_ref = np.random.default_rng(0)
    expected = np.empty(6)
    expected[0] = 0.0
    for t in range(5):
        expected[t + 1] = 0.9 * expected[t] + rng_ref.standard_normal()

    np.testing.assert_allclose(x, expected)


def test_alpha_zero_gives_zero_start():
    rng = np.random.default_rng(7)
    x = simulate(0.0, 500, rng)
    assert x[0] == 0.0


def test_alpha_one_is_random_walk():
    # With alpha=1, x[t+1] = x[t] + eps, so differences should be ~N(0,1)
    rng = np.random.default_rng(99)
    x = simulate(1.0, 10_000, rng)
    diffs = np.diff(x)
    assert abs(diffs.mean()) < 0.1
    assert abs(diffs.std() - 1.0) < 0.05
