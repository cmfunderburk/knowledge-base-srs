"""Tests for srs/scoring.py — pure scoring math."""

import math
import pytest
from knowledge_base.srs.scoring import (
    IntervalResult,
    NORMAL_95_WIDTH,
    COVERAGE_PENALTY,
    score_interval,
    score_point,
    apply_difficulty_modifier,
)


# ---------------------------------------------------------------------------
# TestScoreInterval
# ---------------------------------------------------------------------------

class TestScoreInterval:
    def test_perfect_center_tight_covered(self):
        """Interval centered exactly on true answer, tight width → high score."""
        std = 10.0
        true = 50.0
        lower, upper = 48.0, 52.0
        result = score_interval(lower, upper, true, std)

        assert result.covered is True
        assert result.accuracy_score == pytest.approx(1.0)  # center == true_answer
        # precision_score = exp(-4 / (3.92 * 10)) = exp(-0.1020...)
        expected_precision = math.exp(-4.0 / (NORMAL_95_WIDTH * std))
        assert result.precision_score == pytest.approx(expected_precision)
        expected_core = result.accuracy_score ** 0.5 * result.precision_score ** 0.5
        assert result.score == pytest.approx(expected_core)

    def test_off_center_covered(self):
        """Interval covers true answer but center is off → accuracy_score < 1."""
        std = 10.0
        true = 50.0
        lower, upper = 40.0, 55.0  # center = 47.5, off by 2.5
        result = score_interval(lower, upper, true, std)

        assert result.covered is True
        center = (lower + upper) / 2
        expected_accuracy = math.exp(-abs(true - center) / std)
        assert result.accuracy_score == pytest.approx(expected_accuracy)
        assert result.score > 0.0

    def test_not_covered_penalty(self):
        """True answer outside interval → 0.2x penalty applied."""
        std = 10.0
        true = 80.0
        lower, upper = 40.0, 60.0  # true answer well outside
        result = score_interval(lower, upper, true, std)

        assert result.covered is False
        center = (lower + upper) / 2
        expected_accuracy = math.exp(-abs(true - center) / std)
        expected_precision = math.exp(-(upper - lower) / (NORMAL_95_WIDTH * std))
        expected_core = expected_accuracy ** 0.5 * expected_precision ** 0.5
        assert result.score == pytest.approx(expected_core * COVERAGE_PENALTY)

    def test_very_wide_low_precision(self):
        """Very wide interval → low precision score even if centered."""
        std = 10.0
        true = 50.0
        lower, upper = 0.0, 100.0  # width = 100, much wider than std
        result = score_interval(lower, upper, true, std)

        assert result.covered is True
        assert result.precision_score < 0.1  # wide interval → poor precision
        # Score is penalized by low precision
        tight_result = score_interval(48.0, 52.0, true, std)
        assert result.score < tight_result.score

    def test_tight_off_center_not_covered(self):
        """Tight but wrong interval — not covered and low accuracy."""
        std = 10.0
        true = 50.0
        lower, upper = 20.0, 25.0  # tight, far from true answer
        result = score_interval(lower, upper, true, std)

        assert result.covered is False
        # accuracy is very low (center=22.5, true=50, diff=27.5)
        center = (lower + upper) / 2
        expected_accuracy = math.exp(-abs(true - center) / std)
        assert result.accuracy_score == pytest.approx(expected_accuracy)
        assert result.accuracy_score < 0.1
        assert result.score == pytest.approx(
            result.accuracy_score ** 0.5 * result.precision_score ** 0.5 * COVERAGE_PENALTY
        )


# ---------------------------------------------------------------------------
# TestScorePoint
# ---------------------------------------------------------------------------

class TestScorePoint:
    def test_exact_match(self):
        """Exact match → 1.0."""
        assert score_point(50.0, 50.0, 10.0) == 1.0

    def test_close(self):
        """Error < 0.25 std → 0.5."""
        # error = |50 - 52| / 10 = 0.2, which is < 0.25 but >= 0.05
        assert score_point(52.0, 50.0, 10.0) == 0.5

    def test_wrong(self):
        """Error >= 0.25 std → 0.0."""
        # error = |50 - 55| / 10 = 0.5, which is >= 0.25
        assert score_point(55.0, 50.0, 10.0) == 0.0

    def test_boundary_at_0_05_is_not_1(self):
        """error == 0.05 exactly → 0.5, not 1.0 (boundary is exclusive)."""
        # error = 0.05 * 10 = 0.5 offset
        assert score_point(50.5, 50.0, 10.0) == 0.5

    def test_boundary_at_0_25_is_not_0_5(self):
        """error == 0.25 exactly → 0.0, not 0.5 (boundary is exclusive)."""
        # error = 0.25 * 10 = 2.5 offset
        assert score_point(52.5, 50.0, 10.0) == 0.0


# ---------------------------------------------------------------------------
# TestDifficultyModifier
# ---------------------------------------------------------------------------

class TestDifficultyModifier:
    def test_outlier_bonus(self):
        """True answer 3 std from mean → ~1.3x bonus."""
        score = 0.5
        true_answer = 80.0
        mean = 50.0
        std = 10.0
        # difficulty_z = |80 - 50| / 10 = 3.0
        # modifier = 1 + 0.1 * 3.0 = 1.3
        result = apply_difficulty_modifier(score, true_answer, mean, std)
        assert result == pytest.approx(score * 1.3)

    def test_at_mean_no_change(self):
        """True answer at mean → no bonus, modifier = 1.0."""
        score = 0.6
        result = apply_difficulty_modifier(score, 50.0, 50.0, 10.0)
        assert result == pytest.approx(score * 1.0)

    def test_capped_at_1_0(self):
        """Score * modifier cannot exceed 1.0."""
        # score=0.9, difficulty_z=5 → modifier=1.5 → raw=1.35, should cap at 1.0
        result = apply_difficulty_modifier(0.9, 100.0, 50.0, 10.0)
        assert result == 1.0
