"""Tests for srs/scoring.py — pure scoring math."""

import math
import inspect
import pytest
from knowledge_base.srs.scoring import (
    IntervalResult,
    CI_WIDTH_FACTOR,
    LOGISTIC_CENTER,
    LOGISTIC_SCALE,
    score_interval,
    score_point,
    apply_difficulty_modifier,
)


# ---------------------------------------------------------------------------
# TestScoreInterval
# ---------------------------------------------------------------------------

class TestScoreInterval:
    def test_signature_no_indicator_std(self):
        """score_interval takes exactly 3 positional args (lower, upper, true_answer)."""
        sig = inspect.signature(score_interval)
        params = list(sig.parameters.values())
        assert len(params) == 3
        assert params[0].name == "lower"
        assert params[1].name == "upper"
        assert params[2].name == "true_answer"

    def test_result_fields(self):
        """IntervalResult has z, cov, covered, score."""
        result = score_interval(10.0, 20.0, 13.62)
        assert hasattr(result, "z")
        assert hasattr(result, "cov")
        assert hasattr(result, "covered")
        assert hasattr(result, "score")

    def test_wide_interval_borderline_bad(self):
        """[10, 20] on 13.62 → score 0.35-0.43."""
        result = score_interval(10.0, 20.0, 13.62)
        assert 0.35 <= result.score <= 0.43

    def test_medium_interval_ok(self):
        """[11, 16] on 13.62 → score 0.55-0.63."""
        result = score_interval(11.0, 16.0, 13.62)
        assert 0.55 <= result.score <= 0.63

    def test_tight_interval_borderline_good(self):
        """[12, 15] on 13.62 → score 0.67-0.73."""
        result = score_interval(12.0, 15.0, 13.62)
        assert 0.67 <= result.score <= 0.73

    def test_very_tight_centered_high_score(self):
        """[13, 14.5] on 13.62 → score > 0.78."""
        result = score_interval(13.0, 14.5, 13.62)
        assert result.score > 0.78

    def test_very_wide_bad(self):
        """[0, 30] on 13.62 → score < 0.25."""
        result = score_interval(0.0, 30.0, 13.62)
        assert result.score < 0.25

    def test_not_covered_crushed(self):
        """[20, 25] on 13.62 → covered=False, z > 1.96, score < 0.05."""
        result = score_interval(20.0, 25.0, 13.62)
        assert result.covered is False
        assert result.z > 1.96
        assert result.score < 0.05

    def test_coverage_smooth_not_cliff(self):
        """[10, 14] on 13.99 vs 14.01 → score diff < 0.15 (smooth, not cliff)."""
        result_just_in = score_interval(10.0, 14.0, 13.99)
        result_just_out = score_interval(10.0, 14.0, 14.01)
        assert abs(result_just_in.score - result_just_out.score) < 0.15

    def test_perfect_center_z_zero(self):
        """[48, 52] on 50 → z ≈ 0.0."""
        result = score_interval(48.0, 52.0, 50.0)
        assert result.z == pytest.approx(0.0)

    def test_zero_answer_no_crash(self):
        """[-1, 1] on 0.0 → no crash, score in [0, 1]."""
        result = score_interval(-1.0, 1.0, 0.0)
        assert 0.0 <= result.score <= 1.0

    def test_near_zero_width_centered(self):
        """[49.9999999, 50.0000001] on 50.0 → score = 1.0."""
        result = score_interval(49.9999999, 50.0000001, 50.0)
        assert result.score == pytest.approx(1.0)

    def test_near_zero_width_off_center(self):
        """[99.9999999, 100.0000001] on 50.0 → score < 0.01."""
        result = score_interval(99.9999999, 100.0000001, 50.0)
        assert result.score < 0.01

    def test_score_bounded_zero_one(self):
        """Various intervals → all scores in [0, 1]."""
        cases = [
            (0.0, 100.0, 50.0),
            (45.0, 55.0, 50.0),
            (49.0, 51.0, 50.0),
            (0.0, 10.0, 50.0),
            (100.0, 200.0, 50.0),
            (-50.0, 50.0, 0.0),
        ]
        for lower, upper, true in cases:
            result = score_interval(lower, upper, true)
            assert 0.0 <= result.score <= 1.0, (
                f"score={result.score} out of [0,1] for [{lower},{upper}] on {true}"
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
