# Scoring & Scheduler Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace indicator_std-based Cobb-Douglas scoring with answer-normalized log-likelihood scoring, and eliminate the learning/review state machine in favor of direct FSRS scheduling.

**Architecture:** Pure scoring formula change in `scoring.py` (no external dependencies), scheduler constant updates, DB schema v2 migration dropping `state`/`consecutive_successes` columns, `get_due_cards` rewrite with random ordering for new cards, and TUI simplification removing all state-branching logic.

**Tech Stack:** Python 3.12+, SQLite, pytest, textual

---

### Task 1: Rewrite interval scoring formula

**Files:**
- Modify: `src/knowledge_base/srs/scoring.py`
- Modify: `tests/test_scoring.py`

- [ ] **Step 1: Rewrite test_scoring.py with new tests**

Replace the entire `TestScoreInterval` class and update imports. Keep `TestScorePoint` and `TestDifficultyModifier` unchanged.

```python
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
        """score_interval takes exactly 3 positional args (no indicator_std)."""
        sig = inspect.signature(score_interval)
        assert len(sig.parameters) == 3

    def test_result_fields(self):
        """IntervalResult has z, cov, covered, score."""
        result = score_interval(10.0, 20.0, 13.62)
        assert hasattr(result, "z")
        assert hasattr(result, "cov")
        assert hasattr(result, "covered")
        assert hasattr(result, "score")

    def test_wide_interval_borderline_bad(self):
        """[10, 20] on 13.62 → borderline bad (~0.39)."""
        result = score_interval(10.0, 20.0, 13.62)
        assert result.covered is True
        assert result.z == pytest.approx(0.541, abs=0.01)
        assert result.cov == pytest.approx(0.187, abs=0.01)
        assert 0.35 <= result.score <= 0.43

    def test_medium_interval_ok(self):
        """[11, 16] on 13.62 → OK range (~0.59)."""
        result = score_interval(11.0, 16.0, 13.62)
        assert result.covered is True
        assert 0.55 <= result.score <= 0.63

    def test_tight_interval_borderline_good(self):
        """[12, 15] on 13.62 → borderline good (~0.70)."""
        result = score_interval(12.0, 15.0, 13.62)
        assert result.covered is True
        assert 0.67 <= result.score <= 0.73

    def test_very_tight_centered_high_score(self):
        """[13, 14.5] on 13.62 → good score (~0.82)."""
        result = score_interval(13.0, 14.5, 13.62)
        assert result.covered is True
        assert result.score > 0.78

    def test_very_wide_bad(self):
        """[0, 30] on 13.62 → bad score (~0.19)."""
        result = score_interval(0.0, 30.0, 13.62)
        assert result.covered is True
        assert result.score < 0.25

    def test_not_covered_crushed(self):
        """Answer outside interval → z > 1.96, score near zero."""
        result = score_interval(20.0, 25.0, 13.62)
        assert result.covered is False
        assert result.z > 1.96
        assert result.score < 0.05

    def test_coverage_smooth_not_cliff(self):
        """No discrete penalty cliff at coverage boundary."""
        result_in = score_interval(10.0, 14.0, 13.99)
        result_out = score_interval(10.0, 14.0, 14.01)
        assert result_in.covered is True
        assert result_out.covered is False
        # Scores should be close — no 0.2x multiplier cliff
        assert abs(result_in.score - result_out.score) < 0.15

    def test_perfect_center_z_zero(self):
        """Center == true_answer → z = 0."""
        result = score_interval(48.0, 52.0, 50.0)
        assert result.z == pytest.approx(0.0)
        assert result.covered is True

    def test_zero_answer_no_crash(self):
        """true_answer = 0 should not raise (guarded by epsilon)."""
        result = score_interval(-1.0, 1.0, 0.0)
        assert result.covered is True
        assert 0 <= result.score <= 1

    def test_near_zero_width_centered(self):
        """Near-zero width centered on answer → score = 1.0."""
        result = score_interval(49.9999999, 50.0000001, 50.0)
        assert result.score == pytest.approx(1.0)

    def test_near_zero_width_off_center(self):
        """Near-zero width far from answer → score near 0."""
        result = score_interval(99.9999999, 100.0000001, 50.0)
        assert result.covered is False
        assert result.score < 0.01

    def test_score_bounded_zero_one(self):
        """Score is always in [0, 1]."""
        cases = [
            (10, 20, 13.62),
            (1, 100, 50),
            (49, 51, 50),
            (0, 1000, 500),
        ]
        for lower, upper, answer in cases:
            result = score_interval(lower, upper, answer)
            assert 0 <= result.score <= 1, f"Failed for [{lower}, {upper}] on {answer}"
```

- [ ] **Step 2: Run scoring tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py::TestScoreInterval -v`
Expected: FAIL — imports `CI_WIDTH_FACTOR`, `LOGISTIC_CENTER`, `LOGISTIC_SCALE` don't exist yet, `score_interval` has wrong signature.

- [ ] **Step 3: Implement new score_interval in scoring.py**

Replace the entire contents of `src/knowledge_base/srs/scoring.py`:

```python
"""Scoring functions for SRS interval and point responses."""

import math
from dataclasses import dataclass

CI_WIDTH_FACTOR = 3.92  # 2 * 1.96, width of 95% CI for standard normal
LOGISTIC_CENTER = 2.0   # midpoint of logistic transform
LOGISTIC_SCALE = 1.0    # temperature of logistic transform

_EPSILON = 1e-9  # guard against division by zero


@dataclass
class IntervalResult:
    z: float        # z-score: |A - center| / sigma_implied
    cov: float      # coefficient of variation: sigma_implied / |A|
    covered: bool   # whether A is in [L, U] (informational only)
    score: float    # logistic-transformed log-likelihood


def score_interval(
    lower: float,
    upper: float,
    true_answer: float,
) -> IntervalResult:
    """Score a confidence interval using answer-normalized log-likelihood.

    Treats [lower, upper] as a 95% CI implying N(center, sigma_implied).
    Computes S = -z^2/2 - ln(CoV) and transforms via logistic to [0, 1].

    Coverage penalty emerges naturally from the z-score: if the true answer
    is outside the interval, z > 1.96 and the score is crushed.
    """
    center = (lower + upper) / 2
    width = upper - lower
    sigma_implied = width / CI_WIDTH_FACTOR
    abs_answer = max(abs(true_answer), _EPSILON)

    # Edge case: near-zero width
    if sigma_implied < _EPSILON:
        if abs(true_answer - center) < _EPSILON:
            return IntervalResult(z=0.0, cov=0.0, covered=True, score=1.0)
        return IntervalResult(z=float("inf"), cov=0.0, covered=False, score=0.0)

    z = abs(true_answer - center) / sigma_implied
    cov = sigma_implied / abs_answer
    raw_s = -z**2 / 2 - math.log(cov)
    score = 1.0 / (1.0 + math.exp(-(raw_s - LOGISTIC_CENTER) / LOGISTIC_SCALE))
    covered = lower <= true_answer <= upper

    return IntervalResult(z=z, cov=cov, covered=covered, score=score)


def score_point(user_point: float, true_answer: float, indicator_std: float) -> float:
    """Score a single point-estimate response.

    Returns a discrete score based on how close the guess is relative to the
    indicator standard deviation.

    Returns:
        1.0 if error < 0.05 std, 0.5 if error < 0.25 std, else 0.0.
    """
    error = abs(true_answer - user_point) / indicator_std
    if error < 0.05:
        return 1.0
    if error < 0.25:
        return 0.5
    return 0.0


def apply_difficulty_modifier(
    score: float,
    true_answer: float,
    indicator_mean: float,
    indicator_std: float,
) -> float:
    """Apply a difficulty bonus for unusual true-answer values.

    Questions where the true answer is far from the typical value are harder,
    so correct responses earn a bonus. The result is capped at 1.0.
    """
    difficulty_z = abs(true_answer - indicator_mean) / indicator_std
    modifier = 1 + 0.1 * difficulty_z
    return min(1.0, score * modifier)
```

- [ ] **Step 4: Run scoring tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: ALL PASS (TestScoreInterval, TestScorePoint, TestDifficultyModifier)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scoring.py tests/test_scoring.py
git commit -m "feat: replace indicator_std scoring with answer-normalized log-likelihood"
```

---

### Task 2: Update scheduler constants

**Files:**
- Modify: `src/knowledge_base/srs/scheduler.py`
- Modify: `tests/test_scheduler.py`

- [ ] **Step 1: Update test for new MIN_STABILITY value**

In `tests/test_scheduler.py`, update the import to include `INITIAL_STABILITY` and `INTRA_SESSION_THRESHOLD`, and fix `test_lapse_floors_at_one`:

```python
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
```

Replace `test_lapse_floors_at_one` in `TestUpdateStability`:

```python
    def test_lapse_floors_at_min_stability(self):
        """Lapse from very low stability → floored at MIN_STABILITY (0.1)."""
        # 0.2 * 0.3 = 0.06 < MIN_STABILITY=0.1 → should return 0.1
        s_new = update_stability(0.2, 0.5, 0.1)
        assert s_new == pytest.approx(MIN_STABILITY)
        assert MIN_STABILITY == pytest.approx(0.1)
```

Add new tests at the bottom of the file:

```python
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
```

- [ ] **Step 2: Run scheduler tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `INITIAL_STABILITY` and `INTRA_SESSION_THRESHOLD` don't exist, `MIN_STABILITY` is still 1.0.

- [ ] **Step 3: Update scheduler.py constants**

In `src/knowledge_base/srs/scheduler.py`, change `MIN_STABILITY` and add new constants:

```python
MIN_STABILITY = 0.1
```

Add after `MIN_INTERVAL = 1.0`:

```python
INITIAL_STABILITY = 0.5
INTRA_SESSION_THRESHOLD = 0.05  # days (~1.2 hours); below this, re-queue in-session
```

- [ ] **Step 4: Run scheduler tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat: update scheduler constants (MIN_STABILITY=0.1, add INITIAL_STABILITY)"
```

---

### Task 3: DB schema v2 migration and get_due_cards rewrite

**Files:**
- Modify: `src/knowledge_base/srs/db.py`
- Modify: `tests/test_srs_db.py`

- [ ] **Step 1: Update test_srs_db.py for schema v2**

Replace entire contents of `tests/test_srs_db.py`:

```python
"""Tests for srs/db.py — SQLite schema, CRUD, and migrations."""

import sqlite3
import pytest

from knowledge_base.srs.db import (
    init_db,
    get_schema_version,
    insert_card,
    get_card,
    upsert_card,
    update_card_scheduling,
    get_due_cards,
    insert_review,
    get_reviews_for_card,
    CURRENT_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_card(**overrides) -> dict:
    """Return a minimal valid card dict with sensible defaults."""
    base = {
        "deck": "test_deck",
        "indicator_id": "IND001",
        "entity": "World",
        "era": "2020s",
        "question": "What is X?",
        "answer": 42.0,
    }
    base.update(overrides)
    return base


def _minimal_review(card_id: int, **overrides) -> dict:
    """Return a minimal valid review_log entry."""
    base = {
        "card_id": card_id,
        "timestamp": "2025-01-01T12:00:00",
        "answer_mode": "interval",
        "user_lower": 30.0,
        "user_upper": 50.0,
        "user_point": None,
        "true_answer": 42.0,
        "raw_score": 0.75,
        "desired_retention": 0.90,
        "interval_applied": 3.0,
        "elapsed_days": 0.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_version_is_two(self):
        conn = init_db()
        assert get_schema_version(conn) == 2

    def test_current_schema_version_constant(self):
        assert CURRENT_SCHEMA_VERSION == 2

    def test_cards_table_exists(self):
        conn = init_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cards'"
        ).fetchone()
        assert result is not None

    def test_review_log_table_exists(self):
        conn = init_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='review_log'"
        ).fetchone()
        assert result is not None

    def test_no_state_column(self):
        """v2 schema should not have a state column."""
        conn = init_db()
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "state" not in columns

    def test_no_consecutive_successes_column(self):
        """v2 schema should not have a consecutive_successes column."""
        conn = init_db()
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "consecutive_successes" not in columns

    def test_init_is_idempotent(self):
        conn = init_db()
        from knowledge_base.srs.db import _migrate
        _migrate(conn)
        assert get_schema_version(conn) == 2

    def test_indexes_exist(self):
        conn = init_db()
        index_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_cards_due" in index_names
        assert "idx_cards_deck" in index_names
        assert "idx_review_log_card" in index_names
        assert "idx_review_log_timestamp" in index_names


# ---------------------------------------------------------------------------
# TestCardCRUD
# ---------------------------------------------------------------------------

class TestCardCRUD:
    def test_insert_and_get(self):
        conn = init_db()
        card = _minimal_card()
        card_id = insert_card(conn, card)
        assert isinstance(card_id, int)
        assert card_id > 0

        retrieved = get_card(conn, card_id)
        assert retrieved is not None
        assert retrieved["indicator_id"] == "IND001"
        assert retrieved["entity"] == "World"
        assert retrieved["answer"] == pytest.approx(42.0)

    def test_get_missing_card_returns_none(self):
        conn = init_db()
        assert get_card(conn, 9999) is None

    def test_insert_sets_defaults(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        row = get_card(conn, card_id)
        assert row["reps"] == 0
        assert row["difficulty"] == pytest.approx(0.3)
        assert row["stability"] == pytest.approx(0.5)
        assert row["unit_prefix"] == ""
        assert row["unit_label"] == ""

    def test_unique_constraint_raises(self):
        conn = init_db()
        card = _minimal_card()
        insert_card(conn, card)
        with pytest.raises(sqlite3.IntegrityError):
            insert_card(conn, card)

    def test_upsert_inserts_new(self):
        conn = init_db()
        card = _minimal_card()
        card_id = upsert_card(conn, card)
        assert card_id > 0
        assert get_card(conn, card_id) is not None

    def test_upsert_updates_content_fields(self):
        conn = init_db()
        card = _minimal_card(question="Original question?", answer=10.0)
        card_id = upsert_card(conn, card)

        updated = _minimal_card(question="Updated question?", answer=20.0)
        returned_id = upsert_card(conn, updated)

        assert returned_id == card_id
        row = get_card(conn, card_id)
        assert row["question"] == "Updated question?"
        assert row["answer"] == pytest.approx(20.0)

    def test_upsert_preserves_scheduling_state(self):
        conn = init_db()
        card = _minimal_card()
        card_id = upsert_card(conn, card)

        update_card_scheduling(conn, card_id, {
            "difficulty": 0.55,
            "stability": 7.5,
            "reps": 3,
            "last_review": "2025-01-01T00:00:00",
            "due": "2025-01-08T00:00:00",
        })

        reimported = _minimal_card(question="Revised question?")
        upsert_card(conn, reimported)

        row = get_card(conn, card_id)
        assert row["difficulty"] == pytest.approx(0.55)
        assert row["stability"] == pytest.approx(7.5)
        assert row["reps"] == 3
        assert row["question"] == "Revised question?"


# ---------------------------------------------------------------------------
# TestScheduling
# ---------------------------------------------------------------------------

class TestScheduling:
    def test_update_scheduling_fields(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        update_card_scheduling(conn, card_id, {
            "difficulty": 0.4,
            "stability": 2.5,
            "reps": 1,
            "due": "2025-06-01T00:00:00",
        })

        row = get_card(conn, card_id)
        assert row["difficulty"] == pytest.approx(0.4)
        assert row["stability"] == pytest.approx(2.5)
        assert row["reps"] == 1
        assert row["due"] == "2025-06-01T00:00:00"

    def test_update_scheduling_ignores_unknown_keys(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {"question": "hacked?", "reps": 5})
        row = get_card(conn, card_id)
        assert row["question"] == "What is X?"
        assert row["reps"] == 5

    def test_update_scheduling_ignores_removed_fields(self):
        """state and consecutive_successes are no longer scheduling fields."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        # Should not raise even with old field names
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "consecutive_successes": 5,
            "reps": 2,
        })
        row = get_card(conn, card_id)
        assert row["reps"] == 2

    def test_get_due_cards_returns_new_cards(self):
        """New cards (reps=0) always appear in the due list."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        assert len(due) == 1
        assert due[0]["card_id"] == card_id

    def test_get_due_cards_returns_overdue(self):
        """A reviewed card whose due date is in the past should appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2025-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-06-01T00:00:00")
        assert any(c["card_id"] == card_id for c in due)

    def test_get_due_cards_excludes_future(self):
        """A reviewed card due in the future must not appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2099-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        assert not any(c["card_id"] == card_id for c in due)

    def test_get_due_cards_filters_by_deck(self):
        conn = init_db()
        id_a = insert_card(conn, _minimal_card(deck="deck_a"))
        id_b = insert_card(conn, _minimal_card(
            deck="deck_b", indicator_id="IND002"
        ))

        due_a = get_due_cards(conn, as_of="2025-01-01T00:00:00", deck="deck_a")
        assert len(due_a) == 1
        assert due_a[0]["card_id"] == id_a

    def test_get_due_cards_limit(self):
        conn = init_db()
        for i in range(5):
            insert_card(conn, _minimal_card(
                indicator_id=f"IND{i:03d}",
                entity=f"Entity{i}",
            ))

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00", limit=3)
        assert len(due) == 3

    def test_get_due_cards_overdue_before_new(self):
        """Overdue reviewed cards appear before new cards."""
        conn = init_db()

        new_id = insert_card(conn, _minimal_card(indicator_id="NEW001"))

        overdue_id = insert_card(conn, _minimal_card(
            indicator_id="REV001", entity="E1"
        ))
        update_card_scheduling(conn, overdue_id, {
            "reps": 3,
            "due": "2020-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        card_ids = [c["card_id"] for c in due]
        assert card_ids.index(overdue_id) < card_ids.index(new_id)

    def test_get_due_cards_overdue_ordered_by_due_asc(self):
        """Multiple overdue cards ordered most-overdue-first."""
        conn = init_db()

        old_id = insert_card(conn, _minimal_card(indicator_id="OLD", entity="E1"))
        update_card_scheduling(conn, old_id, {"reps": 1, "due": "2020-01-01T00:00:00"})

        recent_id = insert_card(conn, _minimal_card(indicator_id="REC", entity="E2"))
        update_card_scheduling(conn, recent_id, {"reps": 1, "due": "2024-12-01T00:00:00"})

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        card_ids = [c["card_id"] for c in due]
        assert card_ids.index(old_id) < card_ids.index(recent_id)

    def test_new_cards_randomized(self):
        """New cards should not always be in insertion order (randomized)."""
        conn = init_db()
        ids = []
        for i in range(20):
            cid = insert_card(conn, _minimal_card(
                indicator_id=f"IND{i:03d}", entity=f"Entity{i}"
            ))
            ids.append(cid)

        # Run multiple queries — at least one should differ from insertion order
        orders = set()
        for _ in range(10):
            due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
            order = tuple(c["card_id"] for c in due)
            orders.add(order)

        assert len(orders) > 1, "New cards should be randomized, not always insertion order"


# ---------------------------------------------------------------------------
# TestReviewLog
# ---------------------------------------------------------------------------

class TestReviewLog:
    def test_insert_and_retrieve(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        review = _minimal_review(card_id)

        review_id = insert_review(conn, review)
        assert isinstance(review_id, int)
        assert review_id > 0

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 1
        assert reviews[0]["review_id"] == review_id
        assert reviews[0]["card_id"] == card_id
        assert reviews[0]["raw_score"] == pytest.approx(0.75)

    def test_multiple_reviews_ordered_by_timestamp(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        insert_review(conn, _minimal_review(card_id, timestamp="2025-03-01T10:00:00"))
        insert_review(conn, _minimal_review(card_id, timestamp="2025-01-01T10:00:00"))
        insert_review(conn, _minimal_review(card_id, timestamp="2025-06-01T10:00:00"))

        reviews = get_reviews_for_card(conn, card_id)
        timestamps = [r["timestamp"] for r in reviews]
        assert timestamps == sorted(timestamps)

    def test_get_reviews_empty_for_unknown_card(self):
        conn = init_db()
        assert get_reviews_for_card(conn, 9999) == []

    def test_foreign_key_enforced(self):
        conn = init_db()
        with pytest.raises(sqlite3.IntegrityError):
            insert_review(conn, _minimal_review(card_id=9999))

    def test_file_based_db(self, tmp_path):
        db_file = tmp_path / "test.db"
        conn = init_db(db_file)
        assert get_schema_version(conn) == 2
        card_id = insert_card(conn, _minimal_card())
        assert get_card(conn, card_id) is not None
        conn.close()

        conn2 = init_db(db_file)
        assert get_schema_version(conn2) == 2
        assert get_card(conn2, card_id) is not None


# ---------------------------------------------------------------------------
# TestV1Migration
# ---------------------------------------------------------------------------

class TestV1Migration:
    def _create_v1_db(self):
        """Create a v1 database with state and consecutive_successes columns."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("""
            CREATE TABLE schema_version (version INTEGER NOT NULL)
        """)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("""
            CREATE TABLE cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck TEXT NOT NULL,
                indicator_id TEXT NOT NULL,
                entity TEXT NOT NULL,
                era TEXT NOT NULL,
                question TEXT NOT NULL,
                answer REAL NOT NULL,
                unit_prefix TEXT NOT NULL DEFAULT '',
                unit_label TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                indicator_mean REAL,
                indicator_std REAL,
                scale_factor INTEGER NOT NULL DEFAULT 1,
                decimals INTEGER NOT NULL DEFAULT 0,
                difficulty REAL NOT NULL DEFAULT 0.3,
                stability REAL NOT NULL DEFAULT 1.0,
                last_review TEXT,
                due TEXT,
                reps INTEGER NOT NULL DEFAULT 0,
                consecutive_successes INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'new',
                UNIQUE (indicator_id, entity, era)
            )
        """)
        conn.execute("""
            CREATE TABLE review_log (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL REFERENCES cards(card_id),
                timestamp TEXT NOT NULL,
                answer_mode TEXT NOT NULL,
                user_lower REAL,
                user_upper REAL,
                user_point REAL,
                true_answer REAL NOT NULL,
                raw_score REAL NOT NULL,
                desired_retention REAL NOT NULL,
                interval_applied REAL NOT NULL,
                elapsed_days REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX idx_cards_due ON cards (due, state)")
        conn.execute("CREATE INDEX idx_cards_deck ON cards (deck)")
        conn.execute("CREATE INDEX idx_review_log_card ON review_log (card_id)")
        conn.execute("CREATE INDEX idx_review_log_timestamp ON review_log (timestamp)")
        conn.commit()
        return conn

    def test_v1_migrates_to_v2(self):
        """A v1 database should be migrated to v2 on init."""
        conn = self._create_v1_db()
        # Insert a card with v1 schema
        conn.execute("""
            INSERT INTO cards (deck, indicator_id, entity, era, question, answer,
                               state, consecutive_successes, stability)
            VALUES ('dev', 'gdp', 'India', '2020', 'Q?', 100.0,
                    'learning', 2, 0.3)
        """)
        conn.commit()

        from knowledge_base.srs.db import _migrate
        _migrate(conn)

        assert get_schema_version(conn) == 2

        # state and consecutive_successes columns should be gone
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "state" not in columns
        assert "consecutive_successes" not in columns

        # Card data preserved, stability floored at 0.5
        row = conn.execute("SELECT * FROM cards WHERE entity = 'India'").fetchone()
        assert row is not None
        card = dict(row)
        assert card["stability"] == pytest.approx(0.5)  # was 0.3, floored to 0.5
        assert card["answer"] == pytest.approx(100.0)

    def test_v1_migration_preserves_high_stability(self):
        conn = self._create_v1_db()
        conn.execute("""
            INSERT INTO cards (deck, indicator_id, entity, era, question, answer,
                               stability)
            VALUES ('dev', 'gdp', 'USA', '2020', 'Q?', 50.0, 7.5)
        """)
        conn.commit()

        from knowledge_base.srs.db import _migrate
        _migrate(conn)

        row = conn.execute("SELECT stability FROM cards WHERE entity = 'USA'").fetchone()
        assert row[0] == pytest.approx(7.5)  # kept as-is, above 0.5

    def test_v1_migration_preserves_reviews(self):
        conn = self._create_v1_db()
        conn.execute("""
            INSERT INTO cards (deck, indicator_id, entity, era, question, answer)
            VALUES ('dev', 'gdp', 'India', '2020', 'Q?', 100.0)
        """)
        conn.execute("""
            INSERT INTO review_log (card_id, timestamp, answer_mode, true_answer,
                                    raw_score, desired_retention, interval_applied, elapsed_days)
            VALUES (1, '2025-01-01T00:00:00', 'interval', 100.0, 0.75, 0.9, 3.0, 0.0)
        """)
        conn.commit()

        from knowledge_base.srs.db import _migrate
        _migrate(conn)

        reviews = conn.execute("SELECT * FROM review_log").fetchall()
        assert len(reviews) == 1
        assert dict(reviews[0])["raw_score"] == pytest.approx(0.75)
```

- [ ] **Step 2: Run db tests to verify they fail**

Run: `uv run pytest tests/test_srs_db.py -v`
Expected: FAIL — schema is still v1, state/consecutive_successes columns still exist.

- [ ] **Step 3: Implement schema v2 migration and get_due_cards rewrite in db.py**

Replace entire contents of `src/knowledge_base/srs/db.py`:

```python
"""SQLite persistence layer for the SRS system.

Provides schema creation, CRUD operations, and migration support for the
cards and review_log tables used by the spaced-repetition scheduler.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 2

_DDL_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

_DDL_CARDS = """
CREATE TABLE IF NOT EXISTS cards (
    card_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    deck                    TEXT    NOT NULL,
    indicator_id            TEXT    NOT NULL,
    entity                  TEXT    NOT NULL,
    era                     TEXT    NOT NULL,
    question                TEXT    NOT NULL,
    answer                  REAL    NOT NULL,
    unit_prefix             TEXT    NOT NULL DEFAULT '',
    unit_label              TEXT    NOT NULL DEFAULT '',
    notes                   TEXT    NOT NULL DEFAULT '',
    tags                    TEXT    NOT NULL DEFAULT '[]',
    indicator_mean          REAL,
    indicator_std           REAL,
    scale_factor            INTEGER NOT NULL DEFAULT 1,
    decimals                INTEGER NOT NULL DEFAULT 0,
    difficulty              REAL    NOT NULL DEFAULT 0.3,
    stability               REAL    NOT NULL DEFAULT 0.5,
    last_review             TEXT,
    due                     TEXT,
    reps                    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (indicator_id, entity, era)
);
"""

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS review_log (
    review_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id             INTEGER NOT NULL REFERENCES cards(card_id),
    timestamp           TEXT    NOT NULL,
    answer_mode         TEXT    NOT NULL,
    user_lower          REAL,
    user_upper          REAL,
    user_point          REAL,
    true_answer         REAL    NOT NULL,
    raw_score           REAL    NOT NULL,
    desired_retention   REAL    NOT NULL,
    interval_applied    REAL    NOT NULL,
    elapsed_days        REAL    NOT NULL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_cards_due           ON cards (due, reps);
CREATE INDEX IF NOT EXISTS idx_cards_deck          ON cards (deck);
CREATE INDEX IF NOT EXISTS idx_review_log_card     ON review_log (card_id);
CREATE INDEX IF NOT EXISTS idx_review_log_timestamp ON review_log (timestamp);
"""

# ---------------------------------------------------------------------------
# Scheduling field names — used by update_card_scheduling
# ---------------------------------------------------------------------------

_SCHEDULING_FIELDS = frozenset({
    "difficulty",
    "stability",
    "last_review",
    "due",
    "reps",
})

# Content fields updated on upsert (scheduling state is preserved)
_CONTENT_FIELDS = (
    "deck",
    "question",
    "answer",
    "unit_prefix",
    "unit_label",
    "notes",
    "tags",
    "indicator_mean",
    "indicator_std",
    "scale_factor",
    "decimals",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open (or create) the database and apply migrations.

    Parameters
    ----------
    db_path:
        Filesystem path or ``":memory:"`` for an in-memory database.

    Returns
    -------
    sqlite3.Connection
        A configured connection with WAL journal mode, foreign keys enabled,
        and ``row_factory`` set to ``sqlite3.Row``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Check schema version and apply pending migrations."""
    version = get_schema_version(conn)

    if version == 0:
        _apply_fresh(conn)
    if version == 1:
        _apply_migration_v2(conn)


def _apply_fresh(conn: sqlite3.Connection) -> None:
    """Create all tables from scratch at the current schema version."""
    with conn:
        conn.execute(_DDL_SCHEMA_VERSION)
        conn.execute(_DDL_CARDS)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (CURRENT_SCHEMA_VERSION,),
        )


def _apply_migration_v2(conn: sqlite3.Connection) -> None:
    """Migrate v1 → v2: remove state/consecutive_successes, update defaults."""
    with conn:
        conn.execute("""
            CREATE TABLE cards_v2 (
                card_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                deck                    TEXT    NOT NULL,
                indicator_id            TEXT    NOT NULL,
                entity                  TEXT    NOT NULL,
                era                     TEXT    NOT NULL,
                question                TEXT    NOT NULL,
                answer                  REAL    NOT NULL,
                unit_prefix             TEXT    NOT NULL DEFAULT '',
                unit_label              TEXT    NOT NULL DEFAULT '',
                notes                   TEXT    NOT NULL DEFAULT '',
                tags                    TEXT    NOT NULL DEFAULT '[]',
                indicator_mean          REAL,
                indicator_std           REAL,
                scale_factor            INTEGER NOT NULL DEFAULT 1,
                decimals                INTEGER NOT NULL DEFAULT 0,
                difficulty              REAL    NOT NULL DEFAULT 0.3,
                stability               REAL    NOT NULL DEFAULT 0.5,
                last_review             TEXT,
                due                     TEXT,
                reps                    INTEGER NOT NULL DEFAULT 0,
                UNIQUE (indicator_id, entity, era)
            )
        """)
        conn.execute("""
            INSERT INTO cards_v2 (
                card_id, deck, indicator_id, entity, era, question, answer,
                unit_prefix, unit_label, notes, tags, indicator_mean, indicator_std,
                scale_factor, decimals, difficulty,
                stability, last_review, due, reps
            )
            SELECT
                card_id, deck, indicator_id, entity, era, question, answer,
                unit_prefix, unit_label, notes, tags, indicator_mean, indicator_std,
                scale_factor, decimals, difficulty,
                MAX(stability, 0.5), last_review, due, reps
            FROM cards
        """)
        conn.execute("DROP TABLE cards")
        conn.execute("ALTER TABLE cards_v2 RENAME TO cards")

        # Recreate indexes for v2 schema
        conn.execute("CREATE INDEX idx_cards_due ON cards (due, reps)")
        conn.execute("CREATE INDEX idx_cards_deck ON cards (deck)")

        conn.execute("UPDATE schema_version SET version = 2")


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if the table does not exist."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def insert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new card row and return the generated ``card_id``.

    Raises
    ------
    sqlite3.IntegrityError
        If a card with the same ``(indicator_id, entity, era)`` already exists.
    """
    columns = list(card.keys())
    placeholders = ", ".join("?" * len(columns))
    col_clause = ", ".join(columns)
    values = [card[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO cards ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_card(conn: sqlite3.Connection, card_id: int) -> dict | None:
    """Return the card with ``card_id`` as a plain dict, or ``None``."""
    row = conn.execute(
        "SELECT * FROM cards WHERE card_id = ?", (card_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert or update a card identified by ``(indicator_id, entity, era)``.

    On conflict, content fields are updated but scheduling state
    (difficulty, stability, last_review, due, reps) is preserved.

    Returns
    -------
    int
        The ``card_id`` of the inserted or updated row.
    """
    # Build the INSERT clause (all columns provided)
    columns = list(card.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [card[c] for c in columns]

    # Build the DO UPDATE SET clause — update only content fields present in card
    update_parts = []
    update_values = []
    for field in _CONTENT_FIELDS:
        if field in card:
            update_parts.append(f"{field} = excluded.{field}")

    if not update_parts:
        # Nothing to update — still need to return the existing card_id
        upsert_sql = (
            f"INSERT INTO cards ({col_clause}) VALUES ({placeholders}) "
            "ON CONFLICT (indicator_id, entity, era) DO NOTHING "
            "RETURNING card_id"
        )
        row = conn.execute(upsert_sql, values).fetchone()
        if row:
            conn.commit()
            return row[0]
        # Row already existed and DO NOTHING fired — fetch the id
        existing = conn.execute(
            "SELECT card_id FROM cards WHERE indicator_id=? AND entity=? AND era=?",
            (card["indicator_id"], card["entity"], card["era"]),
        ).fetchone()
        conn.commit()
        return existing[0]

    update_clause = ", ".join(update_parts)
    upsert_sql = (
        f"INSERT INTO cards ({col_clause}) VALUES ({placeholders}) "
        f"ON CONFLICT (indicator_id, entity, era) DO UPDATE SET {update_clause} "
        "RETURNING card_id"
    )
    row = conn.execute(upsert_sql, values).fetchone()
    conn.commit()
    return row[0]


def update_card_scheduling(
    conn: sqlite3.Connection, card_id: int, fields: dict
) -> None:
    """Update only the scheduling columns for the given card.

    Parameters
    ----------
    fields:
        Mapping of column name -> new value. Only recognised scheduling columns
        are accepted; unknown keys are silently ignored.
    """
    allowed = {k: v for k, v in fields.items() if k in _SCHEDULING_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(f"UPDATE cards SET {set_clause} WHERE card_id = ?", values)
    conn.commit()


def get_due_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return cards that are due for review.

    Ordering:
        1. Overdue reviewed cards (reps > 0, due <= as_of) — most overdue first
        2. New cards (reps = 0) — randomized for interleaved practice

    Parameters
    ----------
    as_of:
        ISO-8601 timestamp string used as the cutoff for "now".
    deck:
        Optional deck name filter.
    limit:
        Maximum number of cards to return.
    """
    params: list = [as_of]
    deck_clause = ""
    if deck is not None:
        deck_clause = "AND deck = ?"
        params.append(deck)

    limit_clause = ""
    if limit is not None:
        limit_clause = f"LIMIT {int(limit)}"

    sql = f"""
        SELECT *
        FROM cards
        WHERE (reps = 0 OR (reps > 0 AND due <= ?))
          {deck_clause}
        ORDER BY
            CASE WHEN reps > 0 THEN 0 ELSE 1 END,
            CASE WHEN reps > 0 THEN due END ASC,
            CASE WHEN reps = 0 THEN RANDOM() END
        {limit_clause}
    """

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def insert_review(conn: sqlite3.Connection, review: dict) -> int:
    """Insert a review log entry and return the generated ``review_id``."""
    columns = list(review.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [review[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO review_log ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_reviews_for_card(
    conn: sqlite3.Connection, card_id: int
) -> list[dict]:
    """Return all review log entries for ``card_id``, ordered by timestamp."""
    rows = conn.execute(
        "SELECT * FROM review_log WHERE card_id = ? ORDER BY timestamp ASC",
        (card_id,),
    ).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run db tests to verify they pass**

Run: `uv run pytest tests/test_srs_db.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/db.py tests/test_srs_db.py
git commit -m "feat: schema v2 migration — drop state machine, randomize new cards"
```

---

### Task 4: Update importer for new schema

**Files:**
- Modify: `tests/test_importer.py`
- No changes needed to `src/knowledge_base/srs/importer.py` (it never sets `state` or `consecutive_successes`)

- [ ] **Step 1: Update test_importer.py**

Remove the `test_state_is_new` test from `TestCardFieldsPopulated` (line 172-176). Update `test_scheduling_preserved_on_reimport` in `TestIdempotentReimport` to remove `state` references.

Delete `test_state_is_new`:

```python
# DELETE this entire method from TestCardFieldsPopulated:
    def test_state_is_new(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["state"] == "new"
```

Replace `test_scheduling_preserved_on_reimport`:

```python
    def test_scheduling_preserved_on_reimport(self):
        """Scheduling state set after first import must survive a re-import."""
        from knowledge_base.srs.db import update_card_scheduling

        conn = _make_conn()
        _run_import(conn)

        # Simulate reviewing India's card
        card_id = conn.execute(
            "SELECT card_id FROM cards WHERE entity = 'India'"
        ).fetchone()[0]
        update_card_scheduling(conn, card_id, {
            "reps": 3,
            "stability": 7.5,
        })

        # Re-import
        _run_import(conn)

        # Scheduling should be preserved
        row = dict(conn.execute(
            "SELECT * FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone())
        assert row["reps"] == 3
        assert row["stability"] == pytest.approx(7.5)
```

- [ ] **Step 2: Run importer tests to verify they pass**

Run: `uv run pytest tests/test_importer.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_importer.py
git commit -m "test: update importer tests for schema v2 (remove state references)"
```

---

### Task 5: Simplify TUI review loop and display

**Files:**
- Modify: `src/knowledge_base/srs/tui.py`

- [ ] **Step 1: Update imports in tui.py**

Replace the scheduler imports (line 21-27):

```python
from knowledge_base.srs.scheduler import (
    INTRA_SESSION_THRESHOLD,
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
)
```

Remove `SUCCESS_THRESHOLD` from the import — it's no longer used in the TUI.

- [ ] **Step 2: Replace interval scoring display block**

Replace the interval scoring display (lines 276-296) with:

```python
        if mode == "interval":
            result: IntervalResult = score_interval(val1, val2, true_answer)
            raw_score = result.score

            covered_str = (
                f"[bold green]Yes[/]" if result.covered else "[bold red]No[/]"
            )
            sc_c = _score_color(raw_score)

            display_lines = [
                f"[dim]Answer:[/]   [bold]{_format_display(true_answer, prefix, decimals)}[/]",
                f"[dim]Your range:[/] {_format_display(val1, prefix, decimals)} \u2013 {_format_display(val2, prefix, decimals)}",
                f"[dim]Covered:[/]  {covered_str}",
                "",
                f"[dim]z-score:[/]  {result.z:.2f}    [dim]CoV:[/] {result.cov:.1%}",
                f"[dim]Score:[/]     [{sc_c} bold]{raw_score:.3f}[/]",
            ]
            review_mode = "interval"
            user_lower, user_upper, user_point_val = val1, val2, None
```

- [ ] **Step 3: Move indicator_std check to point-scoring branch only**

Replace the indicator_std guard (lines 269-273) and the point scoring branch so that the guard only applies to point scoring. Remove the guard from its current position (before the if/else). Instead, add it inside the `else` (point) branch:

```python
        if mode == "interval":
            # ... (interval scoring as above — no indicator_std needed)
        else:
            if indicator_std is None or indicator_std == 0:
                self.query_one("#result", Static).update(
                    "[red]Card missing indicator_std; cannot score point prediction.[/red]"
                )
                return
            raw_score = score_point(val1, true_answer, indicator_std)
            label = {1.0: "Perfect", 0.5: "Close", 0.0: "Miss"}[raw_score]
            sc_c = _score_color(raw_score)

            display_lines = [
                f"[dim]Answer:[/]     [bold]{_format_display(true_answer, prefix, decimals)}[/]",
                f"[dim]Your guess:[/] {_format_display(val1, prefix, decimals)}",
                f"[dim]Result:[/]     [{sc_c} bold]{label}[/] [{sc_c}]({raw_score:.1f})[/]",
            ]
            review_mode = "point"
            user_lower, user_upper, user_point_val = None, None, val1
```

- [ ] **Step 4: Replace the scheduling block**

Replace the entire state-branching scheduling block (lines 318-370) with:

```python
        # --- Schedule ---
        now_str = datetime.now(timezone.utc).isoformat()
        old_difficulty = card["difficulty"]
        old_stability = card["stability"]

        # Apply difficulty modifier if enabled
        score = raw_score
        if self.difficulty_modifier and indicator_mean is not None and indicator_std is not None and indicator_std != 0:
            score = apply_difficulty_modifier(raw_score, true_answer, indicator_mean, indicator_std)
            if score != raw_score:
                adj_c = _score_color(score)
                display_lines.append(f"[dim]Adjusted:[/]  [{adj_c} bold]{score:.3f}[/]")

        new_difficulty = update_difficulty(old_difficulty, score)
        new_stability = update_stability(old_stability, new_difficulty, score)
        desired_ret = compute_desired_retention(score)
        interval = compute_interval(new_stability, desired_ret)

        # Compute due date
        from datetime import timedelta
        if interval < INTRA_SESSION_THRESHOLD:
            due_str = now_str
        else:
            due_dt = datetime.now(timezone.utc) + timedelta(days=interval)
            due_str = due_dt.isoformat()

        # Compute elapsed days since last review
        elapsed_days = 0.0
        if card["last_review"]:
            try:
                last_dt = datetime.fromisoformat(card["last_review"])
                elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                elapsed_days = 0.0

        # Update database
        update_card_scheduling(self.conn, card["card_id"], {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "last_review": now_str,
            "due": due_str,
            "reps": card["reps"] + 1,
        })

        insert_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": review_mode,
            "user_lower": user_lower,
            "user_upper": user_upper,
            "user_point": user_point_val,
            "true_answer": true_answer,
            "raw_score": raw_score,
            "desired_retention": desired_ret,
            "interval_applied": interval,
            "elapsed_days": elapsed_days,
        })

        # Display scheduling info
        display_lines.append("")
        if interval < INTRA_SESSION_THRESHOLD:
            display_lines.append("[bold]Next review:[/] [red]again this session[/]")
        elif interval < 1.5:
            display_lines.append("[bold]Next review:[/] 1 day")
        else:
            display_lines.append(f"[bold]Next review:[/] {interval:.0f} days")

        if card.get("notes"):
            display_lines.append("")
            display_lines.append(f"[dim]{card['notes']}[/]")

        self.query_one("#result", Static).update("\n".join(display_lines))
        self.showing_answer = True

        # Re-queue cards with sub-threshold intervals for intra-session repeat
        if interval < INTRA_SESSION_THRESHOLD:
            refreshed = self.conn.execute(
                "SELECT * FROM cards WHERE card_id = ?", (card["card_id"],)
            ).fetchone()
            if refreshed:
                self.cards.append(dict(refreshed))

        # Clear input and keep visible so Enter advances to next card
        inp = self.query_one("#answer-input", Input)
        inp.value = ""
        inp.placeholder = "Enter or Space for next card"
```

Note: The difficulty modifier block moves from after the display_lines construction to before the scheduling. This consolidates all score computation before scheduling.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/tui.py
git commit -m "feat: simplify TUI — remove state machine, show z-score/CoV diagnostics"
```

---

### Task 6: Update integration tests and verify

**Files:**
- Modify: `tests/test_srs_integration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Rewrite test_srs_integration.py**

Replace entire contents:

```python
"""End-to-end SRS integration tests: import -> score -> schedule -> review-log -> stats."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from knowledge_base.srs.db import (
    init_db,
    get_card,
    get_due_cards,
    update_card_scheduling,
    insert_review,
    get_reviews_for_card,
)
from knowledge_base.srs.importer import import_deck
from knowledge_base.srs.scoring import score_interval, score_point
from knowledge_base.srs.scheduler import (
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
    SUCCESS_THRESHOLD,
    INITIAL_STABILITY,
)
from knowledge_base.srs.stats import brier_score, calibration_rate

FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _make_conn():
    return init_db()


def _run_import(conn):
    return import_deck(
        conn,
        deck_key="development",
        data_dir=FIXTURES,
        desc_stats_dir=FIXTURES,
        desc_stats_prefix="desc_stats_",
    )


def _find_india_card(due_cards: list[dict]) -> dict | None:
    for card in due_cards:
        if card["entity"] == "India":
            return card
    return None


# ---------------------------------------------------------------------------
# TestFullReviewCycle
# ---------------------------------------------------------------------------


class TestFullReviewCycle:
    """End-to-end: import -> score -> schedule -> review-log -> verify."""

    def test_import_review_schedule(self):
        """Import, review with good interval, verify FSRS scheduling."""
        conn = _make_conn()
        count = _run_import(conn)
        assert count == 2

        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None, "India card should be due (reps=0)"
        assert india["reps"] == 0

        card_id = india["card_id"]
        true_answer = india["answer"]  # 2389.0

        # Review with a reasonable interval
        r1 = score_interval(1000, 5000, true_answer)
        assert r1.covered is True

        # Schedule via FSRS (no state machine)
        old_difficulty = india["difficulty"]
        old_stability = india["stability"]
        assert old_stability == pytest.approx(INITIAL_STABILITY)

        new_difficulty = update_difficulty(old_difficulty, r1.score)
        new_stability = update_stability(old_stability, new_difficulty, r1.score)
        desired_ret = compute_desired_retention(r1.score)
        interval = compute_interval(new_stability, desired_ret)

        due_date = (date.today() + timedelta(days=int(interval))).isoformat()

        update_card_scheduling(conn, card_id, {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "due": due_date,
            "reps": 1,
            "last_review": TODAY,
        })

        insert_review(conn, {
            "card_id": card_id,
            "timestamp": TODAY + "T00:00:00",
            "answer_mode": "interval",
            "user_lower": 1000.0,
            "user_upper": 5000.0,
            "user_point": None,
            "true_answer": true_answer,
            "raw_score": r1.score,
            "desired_retention": desired_ret,
            "interval_applied": interval,
            "elapsed_days": 0.0,
        })

        card_after = get_card(conn, card_id)
        assert card_after is not None
        assert card_after["reps"] == 1
        assert card_after["stability"] != INITIAL_STABILITY

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 1

    def test_point_prediction_cycle(self):
        """Point prediction with exact-match answer -> score == 1.0."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        assert len(due_cards) > 0

        card = due_cards[0]
        true_answer = card["answer"]
        indicator_std = card["indicator_std"]

        score = score_point(
            user_point=true_answer,
            true_answer=true_answer,
            indicator_std=indicator_std,
        )
        assert score == pytest.approx(1.0)

    def test_stats_from_reviews(self):
        """Insert 3 reviews and verify stats functions."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None
        card_id = india["card_id"]
        true_answer = india["answer"]  # 2389.0

        # Review 1: (1000, 5000) — covers 2389
        r1 = score_interval(1000, 5000, true_answer)
        assert r1.covered is True

        # Review 2: (2000, 3000) — covers 2389
        r2 = score_interval(2000, 3000, true_answer)
        assert r2.covered is True

        # Review 3: (500, 600) — does NOT cover 2389
        r3 = score_interval(500, 600, true_answer)
        assert r3.covered is False

        dr = compute_desired_retention(r1.score)
        for i, (r, lower, upper) in enumerate(
            [(r1, 1000.0, 5000.0), (r2, 2000.0, 3000.0), (r3, 500.0, 600.0)]
        ):
            insert_review(conn, {
                "card_id": card_id,
                "timestamp": f"{TODAY}T0{i}:00:00",
                "answer_mode": "interval",
                "user_lower": lower,
                "user_upper": upper,
                "user_point": None,
                "true_answer": true_answer,
                "raw_score": r.score,
                "desired_retention": compute_desired_retention(r.score),
                "interval_applied": 1.0,
                "elapsed_days": float(i),
            })

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 3

        coverages = [
            row["user_lower"] <= row["true_answer"] <= row["user_upper"]
            for row in reviews
        ]
        assert coverages == [True, True, False]

        bs = brier_score(coverages)
        cr = calibration_rate(coverages)

        assert bs is not None
        assert cr is not None
        assert cr == pytest.approx(2 / 3)

    def test_new_cards_start_at_initial_stability(self):
        """Imported cards should have stability = INITIAL_STABILITY."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        for card in due_cards:
            assert card["stability"] == pytest.approx(INITIAL_STABILITY)
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, update the SRS scoring section under "Key Constraints":

Replace:

```markdown
### SRS scoring
- **Retention modulation is inverted**: good score → *lower* desired retention → *longer* interval. The formula `R_d = 0.90 - 0.05*(score - 0.5)` produces range [0.875, 0.925]. This is because `interval = S * ln(R)/ln(0.9)` and lower R yields a larger ratio.
- **All values stored in display units** (divided by scale_factor). Scoring operates directly on stored values without conversion.
- **Two consecutive successes** (score >= 0.4) required for learning → review promotion.
- **Difficulty modifier** is off by default (`--difficulty-modifier` to enable).
```

With:

```markdown
### SRS scoring
- **Answer-normalized log-likelihood**: interval scoring uses `S = -z²/2 - ln(CoV)` transformed via logistic (`center=2.0, scale=1.0`). No `indicator_std` parameter — depends only on interval bounds and true answer.
- **Retention modulation is inverted**: good score → *lower* desired retention → *longer* interval. The formula `R_d = 0.90 - 0.05*(score - 0.5)` produces range [0.875, 0.925]. This is because `interval = S * ln(R)/ln(0.9)` and lower R yields a larger ratio.
- **All values stored in display units** (divided by scale_factor). Scoring operates directly on stored values without conversion.
- **No state machine**: all cards use FSRS directly. New cards start at `INITIAL_STABILITY = 0.5`. No learning/review distinction or consecutive-success promotion.
- **New cards randomized**: `get_due_cards` returns new cards (reps=0) in random order for interleaved practice.
- **Intra-session repeat**: cards with computed interval < `INTRA_SESSION_THRESHOLD` (0.05 days) are re-queued within the session.
- **Difficulty modifier** is off by default (`--difficulty-modifier` to enable).
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_srs_integration.py CLAUDE.md
git commit -m "test: rewrite integration tests for new scoring + stateless scheduler"
```
