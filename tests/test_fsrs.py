"""Tests for srs/fsrs.py — standard FSRS v6 scheduler with 4-button grading."""

import math
import pytest
from datetime import datetime, timedelta, timezone

from knowledge_base.srs.fsrs import (
    Grade,
    SchedulingResult,
    DECAY,
    FACTOR,
    DESIRED_RETENTION,
    MIN_DIFFICULTY,
    MAX_DIFFICULTY,
    W,
    compute_retrievability,
    compute_interval,
    initial_stability,
    initial_difficulty,
    recall_stability,
    lapse_stability,
    short_term_stability,
    update_difficulty,
    schedule,
)


# ---------------------------------------------------------------------------
# TestRetrievability
# ---------------------------------------------------------------------------

class TestRetrievability:
    def test_just_reviewed(self):
        """elapsed_days=0 -> R=1.0."""
        assert compute_retrievability(0.0, 10.0) == pytest.approx(1.0)

    def test_at_stability(self):
        """elapsed_days == stability -> R = 0.9."""
        assert compute_retrievability(10.0, 10.0) == pytest.approx(0.9)

    def test_zero_stability_returns_zero(self):
        """stability <= 0 -> R = 0.0."""
        assert compute_retrievability(5.0, 0.0) == 0.0
        assert compute_retrievability(5.0, -1.0) == 0.0


# ---------------------------------------------------------------------------
# TestComputeInterval
# ---------------------------------------------------------------------------

class TestComputeInterval:
    def test_interval_approx_stability(self):
        """With R_d=0.9, interval should approximately equal stability."""
        s = 10.0
        i = compute_interval(s)
        assert i == pytest.approx(s, rel=0.01)

    def test_scales_linearly(self):
        """Interval should scale linearly with stability."""
        i1 = compute_interval(10.0)
        i2 = compute_interval(20.0)
        assert i2 == pytest.approx(2 * i1, rel=1e-6)


# ---------------------------------------------------------------------------
# TestInitialStability
# ---------------------------------------------------------------------------

class TestInitialStability:
    def test_again_uses_w0(self):
        """Again grade -> S_0 = W[0]."""
        s = initial_stability(Grade.AGAIN)
        assert s == pytest.approx(W[0])

    def test_good_uses_w2(self):
        """Good grade -> S_0 = W[2]."""
        s = initial_stability(Grade.GOOD)
        assert s == pytest.approx(W[2])

    def test_easy_greater_than_good(self):
        """Easy -> higher initial stability than Good."""
        assert initial_stability(Grade.EASY) > initial_stability(Grade.GOOD)

    def test_ordering(self):
        """Again < Hard < Good < Easy initial stability."""
        stabilities = [initial_stability(g) for g in [Grade.AGAIN, Grade.HARD, Grade.GOOD, Grade.EASY]]
        for i in range(len(stabilities) - 1):
            assert stabilities[i] < stabilities[i + 1]


# ---------------------------------------------------------------------------
# TestInitialDifficulty
# ---------------------------------------------------------------------------

class TestInitialDifficulty:
    def test_all_in_bounds(self):
        """All grades produce difficulty in [1, 10]."""
        for g in Grade:
            d = initial_difficulty(g)
            assert MIN_DIFFICULTY <= d <= MAX_DIFFICULTY

    def test_again_harder_than_easy(self):
        """Again -> higher difficulty than Easy."""
        assert initial_difficulty(Grade.AGAIN) > initial_difficulty(Grade.EASY)

    def test_ordering(self):
        """Again > Hard > Good > Easy initial difficulty."""
        difficulties = [initial_difficulty(g) for g in [Grade.AGAIN, Grade.HARD, Grade.GOOD, Grade.EASY]]
        for i in range(len(difficulties) - 1):
            assert difficulties[i] > difficulties[i + 1]


# ---------------------------------------------------------------------------
# TestRecallStability
# ---------------------------------------------------------------------------

class TestRecallStability:
    def test_good_increases_stability(self):
        """Good grade -> stability increases."""
        s_new = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        assert s_new > 10.0

    def test_hard_less_than_good(self):
        """Hard grade -> less stability increase than Good."""
        s_hard = recall_stability(10.0, 5.0, 0.9, Grade.HARD)
        s_good = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        assert s_hard < s_good

    def test_easy_greater_than_good(self):
        """Easy grade -> more stability increase than Good."""
        s_easy = recall_stability(10.0, 5.0, 0.9, Grade.EASY)
        s_good = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        assert s_easy > s_good


# ---------------------------------------------------------------------------
# TestLapseStability
# ---------------------------------------------------------------------------

class TestLapseStability:
    def test_decreases_stability(self):
        """Lapse -> stability decreases from starting value."""
        s_new = lapse_stability(10.0, 5.0, 0.9)
        assert s_new < 10.0

    def test_higher_difficulty_lower_stability(self):
        """Higher difficulty -> lower post-lapse stability."""
        s_easy = lapse_stability(10.0, 2.0, 0.9)
        s_hard = lapse_stability(10.0, 8.0, 0.9)
        assert s_hard < s_easy


# ---------------------------------------------------------------------------
# TestUpdateDifficulty
# ---------------------------------------------------------------------------

class TestUpdateDifficulty:
    def test_again_increases(self):
        """Again grade -> difficulty increases."""
        d_new = update_difficulty(5.0, Grade.AGAIN)
        assert d_new > 5.0

    def test_easy_decreases(self):
        """Easy grade -> difficulty decreases."""
        d_new = update_difficulty(5.0, Grade.EASY)
        assert d_new < 5.0

    def test_clamped(self):
        """Difficulty stays in [MIN_DIFFICULTY, MAX_DIFFICULTY]."""
        d_low = update_difficulty(MIN_DIFFICULTY, Grade.EASY)
        d_high = update_difficulty(MAX_DIFFICULTY, Grade.AGAIN)
        assert d_low >= MIN_DIFFICULTY
        assert d_high <= MAX_DIFFICULTY


# ---------------------------------------------------------------------------
# TestSchedule
# ---------------------------------------------------------------------------

class TestSchedule:
    def _now(self):
        return datetime.now(timezone.utc)

    def test_first_review_good(self):
        """First review (reps=0) with Good -> result has positive stability and interval."""
        now = self._now()
        result = schedule(
            difficulty=5.0,
            stability=1.0,
            reps=0,
            last_review=None,
            grade=Grade.GOOD,
            now=now,
        )
        assert isinstance(result, SchedulingResult)
        assert result.stability == pytest.approx(W[2])
        assert result.interval > 0
        assert result.reps == 1
        assert result.due is not None

    def test_first_review_again(self):
        """First review (reps=0) with Again -> uses W[0] stability."""
        now = self._now()
        result = schedule(
            difficulty=5.0,
            stability=1.0,
            reps=0,
            last_review=None,
            grade=Grade.AGAIN,
            now=now,
        )
        assert result.stability == pytest.approx(W[0])
        assert result.reps == 1

    def test_established_card_good_increases_stability(self):
        """Established card (reps>0) with Good -> stability increases."""
        now = self._now()
        last_review = now - timedelta(days=10)
        initial_s = 10.0
        result = schedule(
            difficulty=5.0,
            stability=initial_s,
            reps=5,
            last_review=last_review,
            grade=Grade.GOOD,
            now=now,
        )
        assert result.stability > initial_s
        assert result.reps == 6

    def test_established_card_again_decreases_stability(self):
        """Established card (reps>0) with Again -> stability decreases."""
        now = self._now()
        last_review = now - timedelta(days=10)
        initial_s = 10.0
        result = schedule(
            difficulty=5.0,
            stability=initial_s,
            reps=5,
            last_review=last_review,
            grade=Grade.AGAIN,
            now=now,
        )
        assert result.stability < initial_s
        assert result.reps == 6

    def test_result_has_due_date(self):
        """Result always has a non-None due date string."""
        now = self._now()
        result = schedule(
            difficulty=5.0,
            stability=1.0,
            reps=0,
            last_review=None,
            grade=Grade.GOOD,
            now=now,
        )
        assert result.due is not None
        # Should be parseable as ISO-8601
        dt = datetime.fromisoformat(result.due)
        assert dt > now

    def test_same_day_review_non_again(self):
        """Same-day review (elapsed < 1 day, grade != Again) uses short-term stability floor."""
        now = self._now()
        last_review = now - timedelta(hours=1)
        initial_s = 1.0
        result = schedule(
            difficulty=5.0,
            stability=initial_s,
            reps=3,
            last_review=last_review,
            grade=Grade.GOOD,
            now=now,
        )
        # Short-term stability should be >= initial stability (floor applied)
        assert result.stability >= initial_s


def test_compute_interval_accepts_desired_retention_kwarg():
    from knowledge_base.srs.fsrs import compute_interval

    s = 10.0
    default_interval = compute_interval(s)
    high_retention_interval = compute_interval(s, desired_retention=0.95)
    low_retention_interval = compute_interval(s, desired_retention=0.85)

    # Higher retention target → shorter interval (review sooner to keep recall high)
    assert high_retention_interval < default_interval
    assert default_interval < low_retention_interval
    # Default kwarg matches the module constant (0.9)
    assert compute_interval(s) == compute_interval(s, desired_retention=0.9)
