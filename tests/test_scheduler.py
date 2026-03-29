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


from knowledge_base.srs.scheduler import (
    BLEND_CENTER,
    ANCHOR,
    update_stability,
)
from knowledge_base.srs.scheduler import (
    update_stability_short_term,
    update_difficulty,
)


class TestUpdateStability:
    def test_high_score_grows_stability(self):
        """score=0.9 (well above blend_center) -> stability increases."""
        s_new = update_stability(
            stability=10.0, difficulty=5.0, retrievability=0.9, score=0.9,
        )
        assert s_new > 10.0

    def test_zero_score_crashes_stability(self):
        """score=0.0 (100% lapse) -> stability drops dramatically."""
        s_new = update_stability(
            stability=10.0, difficulty=5.0, retrievability=0.9, score=0.0,
        )
        assert s_new < 2.0  # large drop from lapse formula

    def test_mid_score_blends(self):
        """score=0.5 (50/50 blend) -> between pure lapse and pure recall."""
        s_lapse_ish = update_stability(
            stability=10.0, difficulty=5.0, retrievability=0.9, score=0.0,
        )
        s_recall_ish = update_stability(
            stability=10.0, difficulty=5.0, retrievability=0.9, score=0.9,
        )
        s_mid = update_stability(
            stability=10.0, difficulty=5.0, retrievability=0.9, score=0.5,
        )
        assert s_lapse_ish < s_mid < s_recall_ish

    def test_monotonically_increasing_with_score(self):
        """Higher score -> higher new stability."""
        scores = [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]
        stabilities = [
            update_stability(10.0, 5.0, 0.9, s) for s in scores
        ]
        for i in range(len(stabilities) - 1):
            assert stabilities[i] < stabilities[i + 1], (
                f"score {scores[i]} -> {stabilities[i]:.4f} should be < "
                f"score {scores[i+1]} -> {stabilities[i+1]:.4f}"
            )

    def test_gradient_in_low_scores(self):
        """Scores 0.0, 0.2, 0.35 produce meaningfully different stabilities."""
        s0 = update_stability(10.0, 5.0, 0.9, 0.0)
        s2 = update_stability(10.0, 5.0, 0.9, 0.2)
        s35 = update_stability(10.0, 5.0, 0.9, 0.35)
        # Each step should be at least 5% different
        assert (s2 - s0) / s0 > 0.05
        assert (s35 - s2) / s2 > 0.05

    def test_higher_difficulty_slower_recall_growth(self):
        """Higher difficulty -> less stability growth on recall."""
        s_easy = update_stability(10.0, 2.0, 0.9, 0.9)
        s_hard = update_stability(10.0, 8.0, 0.9, 0.9)
        assert s_easy > s_hard

    def test_overdue_card_bigger_gain(self):
        """Lower retrievability (more overdue) -> bigger recall gain (spacing effect)."""
        s_recent = update_stability(10.0, 5.0, 0.9, 0.8)
        s_overdue = update_stability(10.0, 5.0, 0.5, 0.8)
        assert s_overdue > s_recent

    def test_diminishing_returns(self):
        """High stability cards gain less proportionally."""
        s_low = update_stability(1.0, 5.0, 0.9, 0.8)
        s_high = update_stability(100.0, 5.0, 0.9, 0.8)
        ratio_low = s_low / 1.0
        ratio_high = s_high / 100.0
        assert ratio_low > ratio_high

    def test_positive_result(self):
        """Stability is always positive."""
        for score in [0.0, 0.2, 0.5, 0.8, 1.0]:
            s = update_stability(10.0, 5.0, 0.9, score)
            assert s > 0


class TestUpdateStabilityShortTerm:
    def test_passing_score_never_decreases(self):
        """Passing score (>= BLEND_CENTER) should not decrease stability."""
        s_new = update_stability_short_term(1.0, 0.8)
        assert s_new >= 1.0

    def test_high_score_increases(self):
        """High score on same-day review increases stability."""
        s_new = update_stability_short_term(0.01, 0.9)
        assert s_new > 0.01

    def test_convergence_limits_growth(self):
        """Higher starting stability -> smaller proportional gain (convergence)."""
        ratio_low = update_stability_short_term(0.1, 0.9) / 0.1
        ratio_high = update_stability_short_term(10.0, 0.9) / 10.0
        assert ratio_low > ratio_high

    def test_low_score_can_decrease(self):
        """Score well below BLEND_CENTER can decrease stability."""
        s_new = update_stability_short_term(1.0, 0.0)
        assert s_new < 1.0


class TestUpdateDifficulty:
    def test_at_anchor_unchanged(self):
        """score == ANCHOR -> difficulty approximately unchanged."""
        d_new = update_difficulty(5.0, ANCHOR)
        assert d_new == pytest.approx(5.0, abs=0.1)  # mean reversion causes tiny shift

    def test_high_score_lowers(self):
        """score > ANCHOR -> difficulty decreases."""
        d_new = update_difficulty(5.0, 1.0)
        assert d_new < 5.0

    def test_low_score_raises(self):
        """score < ANCHOR -> difficulty increases."""
        d_new = update_difficulty(5.0, 0.0)
        assert d_new > 5.0

    def test_clamped_to_bounds(self):
        """Difficulty stays in [MIN_DIFFICULTY, MAX_DIFFICULTY]."""
        d_low = update_difficulty(MIN_DIFFICULTY, 1.0)
        d_high = update_difficulty(MAX_DIFFICULTY, 0.0)
        assert d_low >= MIN_DIFFICULTY
        assert d_high <= MAX_DIFFICULTY

    def test_mean_reversion(self):
        """Extreme difficulty values get pulled back toward neutral."""
        d_extreme_high = update_difficulty(9.5, ANCHOR)
        d_extreme_low = update_difficulty(1.5, ANCHOR)
        # At anchor score, delta_D = 0, so only mean reversion acts
        # Both should move toward D_0(ANCHOR)
        d_neutral = initial_difficulty(ANCHOR)
        assert d_extreme_high < 9.5  # pulled down
        assert d_extreme_low > 1.5   # pulled up
        # Both should move toward the neutral value
        assert abs(d_extreme_high - d_neutral) < abs(9.5 - d_neutral)
        assert abs(d_extreme_low - d_neutral) < abs(1.5 - d_neutral)

    def test_linear_damping(self):
        """Difficulty change shrinks as D approaches MAX_DIFFICULTY."""
        d_change_mid = abs(update_difficulty(5.0, 0.0) - 5.0)
        d_change_high = abs(update_difficulty(9.0, 0.0) - 9.0)
        assert d_change_mid > d_change_high
