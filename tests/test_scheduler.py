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
