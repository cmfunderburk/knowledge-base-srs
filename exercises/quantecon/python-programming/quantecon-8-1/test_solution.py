import random
import sys

import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_ecdf_exists(sub):
    assert hasattr(sub, "ECDF"), "solution must define a class named 'ECDF'"


def test_stores_observations(sub):
    obs = [1.0, 2.0, 3.0]
    F = sub.ECDF(obs)
    assert hasattr(F, "observations"), "must store as 'self.observations'"
    assert list(F.observations) == obs


def test_callable(sub):
    F = sub.ECDF([1, 2, 3, 4])
    # Must be callable as F(x), i.e. __call__ defined.
    assert F(2.5) == pytest.approx(0.5)


def test_basic_fractions(sub):
    F = sub.ECDF([1, 2, 3, 4])
    assert F(0) == 0.0
    assert F(1) == pytest.approx(0.25)
    assert F(2) == pytest.approx(0.5)
    assert F(3) == pytest.approx(0.75)
    assert F(4) == 1.0
    assert F(5) == 1.0


def test_inclusive_at_x(sub):
    # 1{X_i <= x}, so an observation equal to x is counted.
    F = sub.ECDF([1.0])
    assert F(1.0) == 1.0


def test_reassign_observations(sub):
    F = sub.ECDF([0.0, 1.0])
    F.observations = [10.0, 20.0, 30.0, 40.0]
    assert F(25.0) == pytest.approx(0.5)


def test_converges_to_uniform_cdf(sub):
    rng = random.Random(0xBEEF)
    samples = [rng.random() for _ in range(5000)]
    F = sub.ECDF(samples)
    for x in [0.25, 0.5, 0.75]:
        assert abs(F(x) - x) < 0.05, f"F({x})={F(x):.3f} too far from {x}"
