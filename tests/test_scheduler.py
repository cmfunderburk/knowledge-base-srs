"""Tests for srs/scheduler.py — continuous FSRS scheduling math."""

import math
import pytest
from knowledge_base.srs.scheduler import (
    DECAY,
    FACTOR,
    DESIRED_RETENTION,
    INTRA_SESSION_THRESHOLD,
    compute_retrievability,
    compute_interval,
)


class TestRetrievability:
    def test_just_reviewed(self):
        """elapsed_days=0 -> R=1.0."""
        assert compute_retrievability(0.0, 10.0) == pytest.approx(1.0)

    def test_at_stability(self):
        """elapsed_days == stability -> R = 0.9."""
        assert compute_retrievability(10.0, 10.0) == pytest.approx(0.9)

    def test_double_stability(self):
        """elapsed_days == 2*stability -> R < 0.9."""
        r = compute_retrievability(20.0, 10.0)
        assert r < 0.9
        # Power-law: (1 + FACTOR * 2)^DECAY
        expected = (1 + FACTOR * 2) ** DECAY
        assert r == pytest.approx(expected)

    def test_zero_stability_returns_zero(self):
        """stability <= 0 -> R = 0.0."""
        assert compute_retrievability(5.0, 0.0) == 0.0
        assert compute_retrievability(5.0, -1.0) == 0.0

    def test_power_law_not_exponential(self):
        """Power-law decays slower than exponential at large t."""
        t = 100.0
        s = 10.0
        r_power = compute_retrievability(t, s)
        r_exp = 0.9 ** (t / s)
        assert r_power > r_exp


class TestComputeInterval:
    def test_at_desired_retention(self):
        """When R_d = 0.9, interval = stability."""
        assert compute_interval(10.0) == pytest.approx(10.0)

    def test_scales_with_stability(self):
        """Interval should scale linearly with stability."""
        i1 = compute_interval(10.0)
        i2 = compute_interval(20.0)
        assert i2 == pytest.approx(2 * i1)

    def test_tiny_stability(self):
        """Very small stability still produces a positive interval."""
        interval = compute_interval(0.001)
        assert interval > 0
        assert interval == pytest.approx(0.001)

    def test_factor_and_decay_consistent(self):
        """FACTOR should satisfy 0.9^(1/DECAY) - 1."""
        expected_factor = 0.9 ** (1 / DECAY) - 1
        assert FACTOR == pytest.approx(expected_factor)


from knowledge_base.srs.scheduler import (
    W_BASE,
    W_SCALE,
    initial_stability,
    initial_difficulty,
    MIN_DIFFICULTY,
    MAX_DIFFICULTY,
)


class TestInitialStability:
    def test_zero_score(self):
        """score=0 -> S_0 = W_BASE (~0.0067 days, ~10 min)."""
        s = initial_stability(0.0)
        assert s == pytest.approx(W_BASE)
        assert s * 24 * 60 == pytest.approx(9.6, abs=1.0)  # ~10 min

    def test_perfect_score(self):
        """score=1.0 -> S_0 ~ 6.9 days."""
        s = initial_stability(1.0)
        expected = W_BASE * math.exp(W_SCALE * 1.0)
        assert s == pytest.approx(expected)
        assert s > 5.0  # at least 5 days

    def test_mid_score(self):
        """score=0.5 -> S_0 between zero and perfect."""
        s = initial_stability(0.5)
        assert s > initial_stability(0.0)
        assert s < initial_stability(1.0)

    def test_monotonically_increasing(self):
        """Higher score -> higher initial stability."""
        scores = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        stabilities = [initial_stability(s) for s in scores]
        for i in range(len(stabilities) - 1):
            assert stabilities[i] < stabilities[i + 1]


class TestInitialDifficulty:
    def test_zero_score_hardest(self):
        """score=0 -> D_0 = W4 (highest difficulty for worst performance)."""
        d = initial_difficulty(0.0)
        assert d == pytest.approx(7.0)

    def test_perfect_score_easier(self):
        """score=1.0 -> D_0 < D_0(0)."""
        d = initial_difficulty(1.0)
        assert d < initial_difficulty(0.0)

    def test_clamped_to_bounds(self):
        """Result is always in [MIN_DIFFICULTY, MAX_DIFFICULTY]."""
        for s in [0.0, 0.25, 0.5, 0.75, 1.0]:
            d = initial_difficulty(s)
            assert MIN_DIFFICULTY <= d <= MAX_DIFFICULTY

    def test_monotonically_decreasing(self):
        """Higher score -> lower initial difficulty."""
        scores = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        difficulties = [initial_difficulty(s) for s in scores]
        for i in range(len(difficulties) - 1):
            assert difficulties[i] > difficulties[i + 1]
