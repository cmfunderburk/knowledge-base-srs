"""Tests for srs/stats.py — pure statistical analysis functions."""

import pytest
from knowledge_base.srs.stats import (
    brier_score,
    calibration_rate,
    score_distribution,
    point_hit_rate,
)


# ---------------------------------------------------------------------------
# TestBrierScore
# ---------------------------------------------------------------------------

class TestBrierScore:
    def test_perfect_calibration(self):
        """95 covered + 5 not covered at 95% confidence → ~0.0475."""
        coverages = [True] * 95 + [False] * 5
        result = brier_score(coverages, confidence=0.95)
        # 95 * (0.95 - 1)^2 + 5 * (0.95 - 0)^2 / 100
        expected = (95 * (0.95 - 1.0) ** 2 + 5 * (0.95 - 0.0) ** 2) / 100
        assert result == pytest.approx(expected)

    def test_always_covered(self):
        """All covered at 95% confidence → ~0.0025."""
        coverages = [True] * 100
        result = brier_score(coverages, confidence=0.95)
        # 100 * (0.95 - 1)^2 / 100 = 0.0025
        expected = (0.95 - 1.0) ** 2
        assert result == pytest.approx(expected)

    def test_never_covered(self):
        """None covered at 95% confidence → ~0.9025."""
        coverages = [False] * 100
        result = brier_score(coverages, confidence=0.95)
        # 100 * (0.95 - 0)^2 / 100 = 0.9025
        expected = (0.95 - 0.0) ** 2
        assert result == pytest.approx(expected)

    def test_empty(self):
        """Empty list → None."""
        assert brier_score([]) is None


# ---------------------------------------------------------------------------
# TestCalibrationRate
# ---------------------------------------------------------------------------

class TestCalibrationRate:
    def test_basic(self):
        """[T, T, F, T] → 0.75."""
        coverages = [True, True, False, True]
        assert calibration_rate(coverages) == pytest.approx(0.75)

    def test_empty(self):
        """Empty list → None."""
        assert calibration_rate([]) is None


# ---------------------------------------------------------------------------
# TestScoreDistribution
# ---------------------------------------------------------------------------

class TestScoreDistribution:
    def test_bins(self):
        """6 scores across 5 bins → counts sum to 6."""
        scores = [0.0, 0.15, 0.35, 0.55, 0.75, 1.0]
        result = score_distribution(scores, bins=5)
        assert len(result) == 5
        total = sum(b["count"] for b in result)
        assert total == 6

    def test_empty(self):
        """Empty list → []."""
        assert score_distribution([]) == []

    def test_bin_structure(self):
        """Each bin has lower, upper, count keys."""
        scores = [0.5]
        result = score_distribution(scores, bins=10)
        assert len(result) == 10
        for b in result:
            assert "lower" in b
            assert "upper" in b
            assert "count" in b

    def test_score_1_in_last_bin(self):
        """Score of exactly 1.0 falls in the last bin."""
        scores = [1.0]
        result = score_distribution(scores, bins=10)
        last_bin = result[-1]
        assert last_bin["count"] == 1
        total = sum(b["count"] for b in result)
        assert total == 1


# ---------------------------------------------------------------------------
# TestPointHitRate
# ---------------------------------------------------------------------------

class TestPointHitRate:
    def test_basic(self):
        """[1.0, 1.0, 0.5, 0.0] → perfect=0.5, partial=0.25, miss=0.25."""
        scores = [1.0, 1.0, 0.5, 0.0]
        result = point_hit_rate(scores)
        assert result is not None
        assert result["perfect"] == pytest.approx(0.5)
        assert result["partial"] == pytest.approx(0.25)
        assert result["miss"] == pytest.approx(0.25)

    def test_empty(self):
        """Empty list → None."""
        assert point_hit_rate([]) is None
