# Continuous FSRS Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simplified DSR scheduler with an FSRS v6-inspired scheduler that natively consumes continuous scores in [0,1], producing differentiated intervals across the full score range.

**Architecture:** Full rewrite of `scheduler.py` with 7 pure functions and 23 tunable constants. TUI updated to use new API (first-review vs same-day vs normal branching). DB schema v3 migration updates defaults and clears review history.

**Tech Stack:** Python 3.12+, pytest, SQLite, Textual TUI

**Spec:** `docs/superpowers/specs/2026-03-29-continuous-fsrs-scheduler-design.md`

---

### Task 1: Constants and Forgetting Curve

**Files:**
- Create: `src/knowledge_base/srs/scheduler.py` (full rewrite)
- Create: `tests/test_scheduler.py` (full rewrite)

- [ ] **Step 1: Write failing tests for compute_retrievability**

Replace the entire contents of `tests/test_scheduler.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: ImportError — old scheduler doesn't export DECAY, FACTOR, etc.

- [ ] **Step 3: Implement constants and forgetting curve**

Replace the entire contents of `src/knowledge_base/srs/scheduler.py` with:

```python
"""Continuous FSRS scheduler — FSRS v6-inspired with native continuous score support.

Replaces the simplified DSR model. All formulas accept a continuous score in [0,1]
instead of FSRS's discrete grades (1-4). See design spec:
docs/superpowers/specs/2026-03-29-continuous-fsrs-scheduler-design.md
"""

import math

# ---------------------------------------------------------------------------
# Forgetting curve (FSRS v6 power-law)
# ---------------------------------------------------------------------------

DECAY = -0.5                              # w[20]: forgetting curve decay (v5-compatible)
FACTOR = 0.9 ** (1 / DECAY) - 1          # derived so R(S, S) = 0.9

DESIRED_RETENTION = 0.9                   # constant; score acts through stability

# ---------------------------------------------------------------------------
# Initial stability
# ---------------------------------------------------------------------------

W_BASE = 0.0067                           # S_0 at score=0 (~10 min)
W_SCALE = 6.93                            # S_0 growth rate

# ---------------------------------------------------------------------------
# Initial difficulty
# ---------------------------------------------------------------------------

W4 = 7.0                                  # base initial difficulty
W5 = 0.5                                  # initial difficulty curve shape

# ---------------------------------------------------------------------------
# Difficulty update
# ---------------------------------------------------------------------------

W6 = 1.5                                  # difficulty update magnitude
W7 = 0.01                                 # mean reversion weight
ANCHOR = 0.7                              # difficulty neutral point

# ---------------------------------------------------------------------------
# Recall stability
# ---------------------------------------------------------------------------

W8 = 1.5                                  # recall stability gain (log-scale)
W9 = 0.15                                 # stability diminishing returns exponent
W10 = 1.0                                 # retrievability effect on recall gain
W_SF = 2.0                                # score factor scale (continuous hard/easy)

# ---------------------------------------------------------------------------
# Lapse stability
# ---------------------------------------------------------------------------

W11 = 1.5                                 # post-lapse stability scaling
W12 = 0.1                                 # difficulty effect on post-lapse
W13 = 0.3                                 # pre-lapse S effect on post-lapse
W14 = 2.0                                 # retrievability effect on post-lapse

# ---------------------------------------------------------------------------
# Recall/lapse blend
# ---------------------------------------------------------------------------

BLEND_CENTER = 0.5                        # blend midpoint (50/50 at this score)
BLEND_SCALE = 0.08                        # blend steepness (smaller = sharper)

# ---------------------------------------------------------------------------
# Same-day (short-term) stability
# ---------------------------------------------------------------------------

W17 = 0.5                                 # short-term stability rate
W18 = 0.1                                 # short-term stability offset
W19 = 0.07                                # short-term convergence exponent (v6)

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

INTRA_SESSION_THRESHOLD = 0.05            # days (~1.2 hours); re-queue below this

# ---------------------------------------------------------------------------
# Difficulty bounds
# ---------------------------------------------------------------------------

MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_retrievability(elapsed_days: float, stability: float) -> float:
    """Return retrievability using FSRS v6 power-law forgetting curve.

    R(t, S) = (1 + FACTOR * t/S) ^ DECAY

    Returns 0.0 if stability <= 0.
    """
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def compute_interval(stability: float) -> float:
    """Return next review interval in days.

    I(S) = (S / FACTOR) * (R_d^(1/DECAY) - 1)

    With R_d = 0.9, this simplifies to I = S.
    """
    return (stability / FACTOR) * (DESIRED_RETENTION ** (1 / DECAY) - 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): rewrite with FSRS v6 power-law forgetting curve

Replace exponential R=0.9^(t/S) with power-law R=(1+FACTOR*t/S)^DECAY.
Add all 23 tunable constants. First two functions: compute_retrievability
and compute_interval."
```

---

### Task 2: Initial Stability and Initial Difficulty

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `src/knowledge_base/srs/scheduler.py`

- [ ] **Step 1: Write failing tests for initial_stability and initial_difficulty**

Append to `tests/test_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py::TestInitialStability tests/test_scheduler.py::TestInitialDifficulty -v`
Expected: ImportError — `initial_stability` and `initial_difficulty` not yet defined.

- [ ] **Step 3: Implement initial_stability and initial_difficulty**

Append to `src/knowledge_base/srs/scheduler.py`, after `compute_interval`:

```python
def initial_stability(score: float) -> float:
    """Return initial stability for a first review based on score.

    S_0(s) = W_BASE * e^(W_SCALE * s)
    """
    return W_BASE * math.exp(W_SCALE * score)


def initial_difficulty(score: float) -> float:
    """Return initial difficulty for a first review based on score.

    D_0(s) = W4 - e^(W5 * s * 3) + 1

    Clamped to [MIN_DIFFICULTY, MAX_DIFFICULTY].
    """
    d = W4 - math.exp(W5 * score * 3) + 1
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): add initial_stability and initial_difficulty

Exponential initial stability: S_0(s) = 0.0067 * e^(6.93 * s).
FSRS-adapted initial difficulty with continuous score mapping."
```

---

### Task 3: Stability Update (Recall, Lapse, Blend)

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `src/knowledge_base/srs/scheduler.py`

- [ ] **Step 1: Write failing tests for update_stability**

Append to `tests/test_scheduler.py`:

```python
from knowledge_base.srs.scheduler import (
    BLEND_CENTER,
    ANCHOR,
    update_stability,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py::TestUpdateStability -v`
Expected: ImportError — `update_stability` not yet defined.

- [ ] **Step 3: Implement update_stability**

Append to `src/knowledge_base/srs/scheduler.py`:

```python
def _recall_stability(
    stability: float, difficulty: float, retrievability: float, score: float,
) -> float:
    """Compute stability after successful recall.

    SInc = e^W8 * (11 - D) * S^(-W9) * (e^(W10*(1-R)) - 1) * score_factor(s)
    S_recall = S * (SInc + 1)
    """
    score_factor = math.exp(W_SF * (score - ANCHOR))
    s_inc = (
        math.exp(W8)
        * (11 - difficulty)
        * stability ** (-W9)
        * (math.exp(W10 * (1 - retrievability)) - 1)
        * score_factor
    )
    return stability * (max(s_inc, 0) + 1)


def _lapse_stability(
    stability: float, difficulty: float, retrievability: float,
) -> float:
    """Compute stability after lapse (forgetting).

    S_lapse = W11 * D^(-W12) * ((S+1)^W13 - 1) * e^(W14 * (1-R))
    """
    return (
        W11
        * difficulty ** (-W12)
        * ((stability + 1) ** W13 - 1)
        * math.exp(W14 * (1 - retrievability))
    )


def _blend(score: float) -> float:
    """Return recall weight in [0, 1] using sigmoid centered on BLEND_CENTER.

    blend(s) = 1 / (1 + e^(-(s - BLEND_CENTER) / BLEND_SCALE))
    """
    exponent = -(score - BLEND_CENTER) / BLEND_SCALE
    return 1.0 / (1.0 + math.exp(min(exponent, 709.0)))


def update_stability(
    stability: float,
    difficulty: float,
    retrievability: float,
    score: float,
) -> float:
    """Update stability after a review using recall/lapse blend.

    S_new = blend(s) * S_recall + (1 - blend(s)) * S_lapse
    """
    s_recall = _recall_stability(stability, difficulty, retrievability, score)
    s_lapse = _lapse_stability(stability, difficulty, retrievability)
    b = _blend(score)
    return b * s_recall + (1 - b) * s_lapse
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 26 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): add update_stability with recall/lapse blend

Sigmoid blend replaces binary lapse threshold. Low scores get
proportionally more lapse weight, high scores get pure recall.
Preserves FSRS insights: diminishing returns, spacing effect,
difficulty modulation."
```

---

### Task 4: Same-Day Stability and Difficulty Update

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `src/knowledge_base/srs/scheduler.py`

- [ ] **Step 1: Write failing tests for update_stability_short_term and update_difficulty**

Append to `tests/test_scheduler.py`:

```python
from knowledge_base.srs.scheduler import (
    update_stability_short_term,
    update_difficulty,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py::TestUpdateStabilityShortTerm tests/test_scheduler.py::TestUpdateDifficulty -v`
Expected: ImportError — functions not yet defined.

- [ ] **Step 3: Implement update_stability_short_term and update_difficulty**

Append to `src/knowledge_base/srs/scheduler.py`:

```python
def update_stability_short_term(stability: float, score: float) -> float:
    """Update stability for same-day (short-term) reviews.

    S_short = S * e^(W17 * (s - ANCHOR + W18)) * S^(-W19)

    For passing scores (s >= BLEND_CENTER), multiplier is floored at 1.0.
    """
    multiplier = math.exp(W17 * (score - ANCHOR + W18)) * stability ** (-W19)
    if score >= BLEND_CENTER:
        multiplier = max(multiplier, 1.0)
    return stability * multiplier


def update_difficulty(difficulty: float, score: float) -> float:
    """Update difficulty after a review.

    delta_D = -W6 * (score - ANCHOR)
    D' = D + delta_D * (10 - D) / 9
    D_new = W7 * D_0(ANCHOR) + (1 - W7) * D'

    Clamped to [MIN_DIFFICULTY, MAX_DIFFICULTY].
    """
    delta_d = -W6 * (score - ANCHOR)
    d_prime = difficulty + delta_d * (MAX_DIFFICULTY - difficulty) / 9
    d_anchor = initial_difficulty(ANCHOR)
    d_new = W7 * d_anchor + (1 - W7) * d_prime
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d_new))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 36 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): add short-term stability and difficulty update

Same-day formula with v6 convergence term. Difficulty update with
FSRS mean reversion and linear damping, anchored at 0.7."
```

---

### Task 5: DB Schema v3 Migration

**Files:**
- Modify: `src/knowledge_base/srs/db.py`
- Modify: `tests/test_srs_db.py`

- [ ] **Step 1: Write failing test for schema v3 migration**

Read `tests/test_srs_db.py` to understand existing test patterns, then append:

```python
class TestMigrationV3:
    def test_v2_to_v3_updates_defaults(self):
        """v2 -> v3: difficulty default 7.0, stability default 0.0067."""
        conn = init_db()
        assert get_schema_version(conn) == 3

        # Insert a card with defaults (no explicit difficulty/stability)
        conn.execute("""
            INSERT INTO cards (deck, indicator_id, entity, era, question, answer)
            VALUES ('test', 'ind1', 'ent1', '2020', 'Q?', 42.0)
        """)
        conn.commit()
        row = conn.execute("SELECT difficulty, stability FROM cards WHERE indicator_id='ind1'").fetchone()
        assert row[0] == pytest.approx(7.0)
        assert row[1] == pytest.approx(0.0067)

    def test_v3_review_log_cleared(self):
        """v3 migration should truncate review_log."""
        conn = init_db()
        # review_log should exist but be empty
        count = conn.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        assert count == 0

    def test_fresh_db_is_v3(self):
        """A brand-new database should be at schema version 3."""
        conn = init_db()
        assert get_schema_version(conn) == 3
```

Also update existing imports in the test file to include `get_schema_version`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_srs_db.py::TestMigrationV3 -v`
Expected: FAIL — schema version is still 2, defaults are old values.

- [ ] **Step 3: Implement schema v3 migration**

In `src/knowledge_base/srs/db.py`, make these changes:

1. Update `CURRENT_SCHEMA_VERSION = 3`

2. Update the `_DDL_CARDS` default values:
   - Change `difficulty REAL NOT NULL DEFAULT 0.3` to `difficulty REAL NOT NULL DEFAULT 7.0`
   - Change `stability REAL NOT NULL DEFAULT 0.5` to `stability REAL NOT NULL DEFAULT 0.0067`

3. Update `_migrate` to apply v3:

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Check schema version and apply pending migrations."""
    version = get_schema_version(conn)

    if version == 0:
        _apply_fresh(conn)

    if get_schema_version(conn) == 1:
        _apply_migration_v2(conn)

    if get_schema_version(conn) == 2:
        _apply_migration_v3(conn)
```

4. Add the v3 migration function:

```python
def _apply_migration_v3(conn: sqlite3.Connection) -> None:
    """Upgrade v2 -> v3: update defaults for continuous FSRS, clear review_log."""
    conn.execute("PRAGMA foreign_keys=OFF;")
    try:
        with conn:
            conn.execute("""
                CREATE TABLE cards_v3 (
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
                    difficulty              REAL    NOT NULL DEFAULT 7.0,
                    stability               REAL    NOT NULL DEFAULT 0.0067,
                    last_review             TEXT,
                    due                     TEXT,
                    reps                    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (indicator_id, entity, era)
                )
            """)

            conn.execute("""
                INSERT INTO cards_v3
                    (card_id, deck, indicator_id, entity, era, question, answer,
                     unit_prefix, unit_label, notes, tags, indicator_mean,
                     indicator_std, scale_factor, decimals, difficulty,
                     stability, last_review, due, reps)
                SELECT
                    card_id, deck, indicator_id, entity, era, question, answer,
                    unit_prefix, unit_label, notes, tags, indicator_mean,
                    indicator_std, scale_factor, decimals, difficulty,
                    stability, last_review, due, reps
                FROM cards
            """)

            conn.execute("DROP TABLE cards")
            conn.execute("ALTER TABLE cards_v3 RENAME TO cards")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_due  ON cards (due, reps)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards (deck)"
            )

            # Clear review history for clean slate
            conn.execute("DELETE FROM review_log")

            conn.execute("UPDATE schema_version SET version = 3")
    finally:
        conn.execute("PRAGMA foreign_keys=ON;")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_srs_db.py -v`
Expected: All tests PASS (including new v3 tests and existing tests that now use v3)

- [ ] **Step 5: Run full test suite to check for breakage**

Run: `uv run pytest -v`
Expected: Some tests in `test_srs_integration.py` and possibly `test_importer.py` may fail because they reference old scheduler constants. That's expected — we fix those in Tasks 7-8.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/db.py tests/test_srs_db.py
git commit -m "feat(db): schema v3 — update defaults for continuous FSRS

Difficulty default 7.0 (was 0.3), stability default 0.0067 (was 0.5).
Truncates review_log for clean slate."
```

---

### Task 6: TUI Integration

**Files:**
- Modify: `src/knowledge_base/srs/tui.py`

- [ ] **Step 1: Update TUI imports**

Replace the scheduler imports at the top of `tui.py`:

```python
from knowledge_base.srs.scheduler import (
    INTRA_SESSION_THRESHOLD,
    compute_retrievability,
    compute_interval,
    initial_stability,
    initial_difficulty,
    update_stability,
    update_stability_short_term,
    update_difficulty,
)
```

Remove the old imports: `compute_desired_retention`, `update_stability` (old signature), `update_difficulty` (old signature).

- [ ] **Step 2: Update scheduling block in on_input_submitted**

Replace the scheduling section in `on_input_submitted` (lines ~308-349 in current tui.py, from `# --- Schedule ---` through the `update_card_scheduling` call) with:

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

        # Compute elapsed days since last review
        elapsed_days = 0.0
        if card["last_review"]:
            try:
                last_dt = datetime.fromisoformat(card["last_review"])
                elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                elapsed_days = 0.0

        # Compute new scheduling state
        if card["reps"] == 0:
            # First review: use initial functions
            new_stability = initial_stability(score)
            new_difficulty = initial_difficulty(score)
        elif elapsed_days < 1.0:
            # Same-day review: use short-term formula
            new_stability = update_stability_short_term(old_stability, score)
            new_difficulty = update_difficulty(old_difficulty, score)
        else:
            # Normal review: full recall/lapse blend
            retrievability = compute_retrievability(elapsed_days, old_stability)
            new_stability = update_stability(old_stability, old_difficulty, retrievability, score)
            new_difficulty = update_difficulty(old_difficulty, score)

        interval = compute_interval(new_stability)

        # Compute due date
        from datetime import timedelta
        if interval < INTRA_SESSION_THRESHOLD:
            due_str = now_str
        else:
            due_dt = datetime.now(timezone.utc) + timedelta(days=interval)
            due_str = due_dt.isoformat()

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
            "desired_retention": 0.9,
            "interval_applied": interval,
            "elapsed_days": elapsed_days,
        })
```

- [ ] **Step 3: Commit**

```bash
git add src/knowledge_base/srs/tui.py
git commit -m "feat(tui): integrate continuous FSRS scheduler

Three-branch scheduling: initial (reps=0), same-day (elapsed<1),
normal (full blend). Desired retention now constant 0.9."
```

---

### Task 7: Update Integration Tests

**Files:**
- Modify: `tests/test_srs_integration.py`

- [ ] **Step 1: Update integration test imports and assertions**

Replace the entire contents of `tests/test_srs_integration.py` with:

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
    W_BASE,
    compute_interval,
    initial_stability,
    initial_difficulty,
    update_stability,
    update_difficulty,
    compute_retrievability,
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
        """Import, review with good interval, verify continuous FSRS scheduling."""
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

        # Schedule via continuous FSRS (first review)
        old_stability = india["stability"]
        assert old_stability == pytest.approx(W_BASE)

        new_stability = initial_stability(r1.score)
        new_difficulty = initial_difficulty(r1.score)
        interval = compute_interval(new_stability)

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
            "desired_retention": 0.9,
            "interval_applied": interval,
            "elapsed_days": 0.0,
        })

        card_after = get_card(conn, card_id)
        assert card_after is not None
        assert card_after["reps"] == 1
        assert card_after["stability"] != W_BASE

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
                "desired_retention": 0.9,
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

    def test_new_cards_start_at_w_base(self):
        """Imported cards should have stability = W_BASE."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        for card in due_cards:
            assert card["stability"] == pytest.approx(W_BASE)

    def test_score_differentiation_on_new_cards(self):
        """Different scores on new cards produce different intervals."""
        conn = _make_conn()
        _run_import(conn)

        s_low = initial_stability(0.0)
        s_mid = initial_stability(0.35)
        s_high = initial_stability(0.8)

        i_low = compute_interval(s_low)
        i_mid = compute_interval(s_mid)
        i_high = compute_interval(s_high)

        # All should be meaningfully different
        assert i_low < i_mid < i_high
        # Low score should be sub-hour, high score should be multi-day
        assert i_low < 1.0 / 24  # less than 1 hour
        assert i_high > 1.0      # more than 1 day
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_srs_integration.py
git commit -m "test: update integration tests for continuous FSRS scheduler

Replace INITIAL_STABILITY/SUCCESS_THRESHOLD references with W_BASE.
Add test_score_differentiation_on_new_cards to verify the core problem
is solved: different scores produce different intervals."
```

---

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the SRS scoring section in CLAUDE.md**

Replace the `### SRS scoring` section under `## Key Constraints` with updated documentation reflecting the new scheduler constants, the continuous blend, and the FSRS v6 power-law curve. Key points to document:

- Power-law forgetting curve replaces exponential
- Continuous score → stability via sigmoid blend (no binary threshold)
- `ANCHOR = 0.7` — difficulty neutral point
- `BLEND_CENTER = 0.5` — recall/lapse blend midpoint
- `W_BASE = 0.0067`, `W_SCALE = 6.93` — initial stability curve
- Desired retention is constant 0.9
- Difficulty range [1, 10]
- Same-day formula with convergence term
- `INTRA_SESSION_THRESHOLD = 0.05` unchanged
- All 23 parameters in `scheduler.py` with docstrings

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for continuous FSRS scheduler

Document power-law forgetting curve, sigmoid blend, anchor/blend_center
constants, and updated parameter set."
```
