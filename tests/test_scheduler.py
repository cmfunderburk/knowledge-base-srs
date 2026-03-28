"""Tests for srs/scheduler.py — pure FSRS scheduling math."""

import math
import pytest
from knowledge_base.srs.scheduler import (
    BASE_RETENTION,
    MIN_INTERVAL,
    LAPSE_FACTOR,
    MIN_STABILITY,
    INITIAL_STABILITY,
    INTRA_SESSION_THRESHOLD,
    compute_retrievability,
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
)


# ---------------------------------------------------------------------------
# TestRetrievability
# ---------------------------------------------------------------------------

class TestRetrievability:
    def test_just_reviewed(self):
        """elapsed_days=0 → R=1.0 regardless of stability."""
        assert compute_retrievability(0.0, 10.0) == pytest.approx(1.0)

    def test_at_stability(self):
        """elapsed_days == stability → R = 0.9."""
        assert compute_retrievability(10.0, 10.0) == pytest.approx(0.9)

    def test_double_stability(self):
        """elapsed_days == 2 * stability → R = 0.9^2 = 0.81."""
        assert compute_retrievability(20.0, 10.0) == pytest.approx(0.81)

    def test_zero_stability_returns_zero(self):
        """stability <= 0 → R = 0.0."""
        assert compute_retrievability(5.0, 0.0) == 0.0
        assert compute_retrievability(5.0, -1.0) == 0.0


# ---------------------------------------------------------------------------
# TestDesiredRetention
# ---------------------------------------------------------------------------

class TestDesiredRetention:
    def test_baseline(self):
        """score=0.5 → 0.90 (no shift)."""
        assert compute_desired_retention(0.5) == pytest.approx(0.90)

    def test_perfect(self):
        """score=1.0 → 0.90 - 0.05*0.5 = 0.875 (lower target → longer interval)."""
        assert compute_desired_retention(1.0) == pytest.approx(0.875)

    def test_zero(self):
        """score=0.0 → 0.90 - 0.05*(-0.5) = 0.925 (higher target → shorter interval)."""
        assert compute_desired_retention(0.0) == pytest.approx(0.925)

    def test_range_check(self):
        """Result is always in [0.875, 0.925]."""
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            r = compute_desired_retention(score)
            assert 0.875 <= r <= 0.925


# ---------------------------------------------------------------------------
# TestComputeInterval
# ---------------------------------------------------------------------------

class TestComputeInterval:
    def test_at_base_retention(self):
        """desired_retention == 0.9 → interval ≈ stability."""
        stability = 10.0
        interval = compute_interval(stability, BASE_RETENTION)
        assert interval == pytest.approx(stability)

    def test_lower_retention_longer(self):
        """Lower desired retention → longer interval (less frequent review needed)."""
        stability = 10.0
        base_interval = compute_interval(stability, 0.90)
        lower_interval = compute_interval(stability, 0.80)
        assert lower_interval > base_interval

    def test_higher_retention_shorter(self):
        """Higher desired retention → shorter interval (must review more often)."""
        stability = 10.0
        base_interval = compute_interval(stability, 0.90)
        higher_interval = compute_interval(stability, 0.92)
        assert higher_interval < base_interval

    def test_minimum_floor(self):
        """Very short stability always returns at least MIN_INTERVAL."""
        interval = compute_interval(0.01, 0.90)
        assert interval == pytest.approx(MIN_INTERVAL)

    def test_invalid_retention_returns_minimum(self):
        """desired_retention <= 0 or >= 1 → MIN_INTERVAL."""
        assert compute_interval(10.0, 0.0) == MIN_INTERVAL
        assert compute_interval(10.0, 1.0) == MIN_INTERVAL
        assert compute_interval(10.0, -0.1) == MIN_INTERVAL


# ---------------------------------------------------------------------------
# TestUpdateDifficulty
# ---------------------------------------------------------------------------

class TestUpdateDifficulty:
    def test_good_score_lowers(self):
        """score > DIFFICULTY_ANCHOR (0.7) → difficulty decreases."""
        d = update_difficulty(0.5, 0.9)
        assert d < 0.5

    def test_bad_score_raises(self):
        """score < DIFFICULTY_ANCHOR (0.7) → difficulty increases."""
        d = update_difficulty(0.5, 0.2)
        assert d > 0.5

    def test_clamped_low(self):
        """Very low starting difficulty with good score → clamps at MIN_DIFFICULTY."""
        # MIN_DIFFICULTY=0.05, start at 0.05, score=1.0
        # d_new = 0.05 + 0.1*(0.7 - 1.0) = 0.05 - 0.03 = 0.02 → clamped to 0.05
        d = update_difficulty(0.05, 1.0)
        assert d == pytest.approx(0.05)

    def test_clamped_high(self):
        """Very high starting difficulty with bad score → clamps at MAX_DIFFICULTY."""
        # MAX_DIFFICULTY=1.0, start at 1.0, score=0.0
        # d_new = 1.0 + 0.1*(0.7 - 0.0) = 1.0 + 0.07 = 1.07 → clamped to 1.0
        d = update_difficulty(1.0, 0.0)
        assert d == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestUpdateStability
# ---------------------------------------------------------------------------

class TestUpdateStability:
    def test_successful_grows(self):
        """score >= SUCCESS_THRESHOLD → stability increases."""
        s_new = update_stability(10.0, 0.5, 0.8)
        assert s_new > 10.0

    def test_lapse_drops(self):
        """score < SUCCESS_THRESHOLD → S_new = S * LAPSE_FACTOR."""
        s_new = update_stability(10.0, 0.5, 0.2)
        assert s_new == pytest.approx(10.0 * LAPSE_FACTOR)

    def test_lapse_floors_at_min_stability(self):
        """Lapse from very low stability → floored at MIN_STABILITY (0.1)."""
        # 0.2 * 0.3 = 0.06 < MIN_STABILITY=0.1 → should return 0.1
        s_new = update_stability(0.2, 0.5, 0.1)
        assert s_new == pytest.approx(MIN_STABILITY)
        assert MIN_STABILITY == pytest.approx(0.1)

    def test_lower_difficulty_faster_growth(self):
        """Lower difficulty → larger stability gain on success."""
        s_low_d = update_stability(10.0, 0.2, 0.8)   # low difficulty
        s_high_d = update_stability(10.0, 0.8, 0.8)  # high difficulty
        assert s_low_d > s_high_d


# ---------------------------------------------------------------------------
# TestSchedulerConstants
# ---------------------------------------------------------------------------

class TestSchedulerConstants:
    def test_min_stability_value(self):
        assert MIN_STABILITY == pytest.approx(0.1)

    def test_initial_stability_value(self):
        assert INITIAL_STABILITY == pytest.approx(0.5)

    def test_intra_session_threshold_value(self):
        assert INTRA_SESSION_THRESHOLD == pytest.approx(0.05)

    def test_initial_above_min(self):
        """INITIAL_STABILITY must be above MIN_STABILITY."""
        assert INITIAL_STABILITY > MIN_STABILITY
