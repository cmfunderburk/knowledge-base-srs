# Code-Review FSRS Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Leitner scheduling in `code_review` with Anki-style FSRS: learning steps (1m / 10m / 4h / 12h), lapse steps (30m / 4h), desired retention 0.95.

**Architecture:** New `code_review/scheduler.py` holds a 3-phase state machine (LEARNING / REVIEW / RELEARNING) over a `CardState` dataclass. FSRS math (initial / recall / lapse / short-term stability, difficulty update) is reused from the existing `srs/fsrs.py` after a one-line parameterization of `compute_interval` to accept retention. DB schema is rewritten (no preservation — only 4 exercises, 6 review-log rows to discard). TUI keeps its current screens; the grade callback swaps Leitner for the new scheduler.

**Tech Stack:** Python 3.12+, `uv`, `pytest`, `textual` (no new deps).

**Spec:** `docs/superpowers/specs/2026-05-18-code-review-fsrs-port-design.md`

---

## File Structure

**New files:**
- `src/knowledge_base/code_review/scheduler.py` — state machine, constants, `CardState`, `ScheduleResult`, `schedule()`, `initial_state()`
- `tests/code_review/test_scheduler.py` — replaces `test_leitner.py`

**Modified files:**
- `src/knowledge_base/srs/fsrs.py` — `compute_interval` accepts `desired_retention` kwarg
- `src/knowledge_base/code_review/db.py` — new schema; migration drops old tables on `box` detection
- `src/knowledge_base/code_review/tui.py` — grade callback uses `scheduler.schedule`; due-time display & learn-ahead
- `tests/code_review/test_db.py` — schema, migration, `record_grade` tests rewritten for new schema
- `tests/code_review/test_tui_grouping.py` — labels updated from `box` to `phase` where they appear
- `tests/test_fsrs.py` — add parameterized retention test
- `CLAUDE.md` — Quick Reference + Key Constraints updated

**Deleted files:**
- `src/knowledge_base/code_review/leitner.py`
- `tests/code_review/test_leitner.py`

---

## Task 1: Parameterize `compute_interval` retention

**Files:**
- Modify: `src/knowledge_base/srs/fsrs.py` (function `compute_interval`)
- Modify: `tests/test_fsrs.py`

- [ ] **Step 1: Add failing test for parameterized retention**

Append to `tests/test_fsrs.py`:

```python
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
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_fsrs.py::test_compute_interval_accepts_desired_retention_kwarg -v
```

Expected: FAIL with `TypeError: compute_interval() got an unexpected keyword argument 'desired_retention'`.

- [ ] **Step 3: Parameterize `compute_interval` in `src/knowledge_base/srs/fsrs.py`**

Replace the existing `compute_interval` function with:

```python
def compute_interval(stability: float, desired_retention: float = DESIRED_RETENTION) -> float:
    """Return next review interval in days.

    I(S) = (S / FACTOR) * (R_d^(1/DECAY) - 1)

    With R_d = 0.9, this simplifies to I ≈ S.
    """
    return (stability / FACTOR) * (desired_retention ** (1 / DECAY) - 1)
```

Also update the internal call site if any other function in this module calls `compute_interval` — search the file for `compute_interval(`. The only existing call is inside `schedule(...)` itself; it passes no retention kwarg, so it continues to use 0.9. Leave it as-is.

- [ ] **Step 4: Run test, confirm it passes**

```bash
uv run pytest tests/test_fsrs.py::test_compute_interval_accepts_desired_retention_kwarg -v
```

Expected: PASS.

- [ ] **Step 5: Run full FSRS test suite to confirm no regressions**

```bash
uv run pytest tests/test_fsrs.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/fsrs.py tests/test_fsrs.py
git commit -m "$(cat <<'EOF'
feat(fsrs): parameterize compute_interval retention

Allows callers to pass desired_retention as a kwarg without mutating
the module constant. Default behavior unchanged (uses DESIRED_RETENTION=0.9).
Code-review will pass 0.95.
EOF
)"
```

---

## Task 2: Scheduler skeleton (types, constants, `initial_state`)

**Files:**
- Create: `src/knowledge_base/code_review/scheduler.py`
- Create: `tests/code_review/test_scheduler.py`

- [ ] **Step 1: Write failing tests for skeleton**

Create `tests/code_review/test_scheduler.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from knowledge_base.code_review.scheduler import (
    CardState,
    LEARNING_STEPS_SEC,
    LEARN_AHEAD_SEC,
    Phase,
    RELEARNING_STEPS_SEC,
    DESIRED_RETENTION,
    initial_state,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_constants_match_anki_config():
    assert LEARNING_STEPS_SEC == [60, 600, 14400, 43200]
    assert RELEARNING_STEPS_SEC == [1800, 14400]
    assert LEARN_AHEAD_SEC == 1200
    assert DESIRED_RETENTION == 0.95


def test_phase_enum_values():
    assert Phase.LEARNING == 1
    assert Phase.REVIEW == 2
    assert Phase.RELEARNING == 3


def test_initial_state_fresh_card():
    state = initial_state(NOW)
    assert state.phase == Phase.LEARNING
    assert state.step_index == 0
    assert state.stability == 0.0
    assert state.difficulty == 0.0
    assert state.reps == 0
    assert state.last_review is None
    assert state.due == NOW.isoformat()
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_base.code_review.scheduler'`.

- [ ] **Step 3: Create `src/knowledge_base/code_review/scheduler.py` skeleton**

```python
"""FSRS-with-learning-steps scheduler for code-review exercises.

State machine: LEARNING → REVIEW → (RELEARNING → REVIEW)*. Pure functions
over CardState. FSRS math (stability/difficulty) is delegated to
knowledge_base.srs.fsrs; this module owns the learning/relearning step
sequencing and the lapse-time stability storage convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from knowledge_base.srs.fsrs import (
    Grade,
    compute_interval,
    initial_difficulty,
    initial_stability,
    lapse_stability,
    recall_stability,
    update_difficulty,
)


# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------

class Phase(IntEnum):
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


# ---------------------------------------------------------------------------
# Anki-matched configuration constants
# ---------------------------------------------------------------------------

LEARNING_STEPS_SEC: list[int] = [60, 600, 14400, 43200]      # 1m, 10m, 4h, 12h
RELEARNING_STEPS_SEC: list[int] = [1800, 14400]              # 30m, 4h
DESIRED_RETENTION: float = 0.95
LEARN_AHEAD_SEC: int = 1200                                  # 20m, Anki collapseTime default


# ---------------------------------------------------------------------------
# State dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CardState:
    phase: Phase
    step_index: int
    stability: float
    difficulty: float
    reps: int
    last_review: str | None  # ISO-8601 UTC, None if reps == 0
    due: str                 # ISO-8601 UTC


@dataclass
class ScheduleResult:
    phase: Phase
    step_index: int
    stability: float
    difficulty: float
    reps: int
    last_review: str
    due: str


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def initial_state(now: datetime) -> CardState:
    """Return a fresh card: LEARNING phase, step 0, due now."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return CardState(
        phase=Phase.LEARNING,
        step_index=0,
        stability=0.0,
        difficulty=0.0,
        reps=0,
        last_review=None,
        due=now.isoformat(),
    )
```

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/scheduler.py tests/code_review/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat(code-review): scheduler module skeleton

Phase enum, Anki-matched constants, CardState/ScheduleResult dataclasses,
initial_state() helper. No transitions yet.
EOF
)"
```

---

## Task 3: LEARNING phase transitions

**Files:**
- Modify: `src/knowledge_base/code_review/scheduler.py` (add `schedule()` with LEARNING dispatch)
- Modify: `tests/code_review/test_scheduler.py`

- [ ] **Step 1: Write failing tests for LEARNING transitions**

Append to `tests/code_review/test_scheduler.py`:

```python
from knowledge_base.code_review.scheduler import schedule
from knowledge_base.srs.fsrs import Grade, initial_difficulty, initial_stability


def _learning_state(step_index: int = 0) -> CardState:
    return CardState(
        phase=Phase.LEARNING,
        step_index=step_index,
        stability=0.0,
        difficulty=0.0,
        reps=0,
        last_review=None,
        due=NOW.isoformat(),
    )


def _seconds_until(now: datetime, due_iso: str) -> int:
    due = datetime.fromisoformat(due_iso)
    return round((due - now).total_seconds())


def test_learning_again_resets_to_step_0_with_1m_delay():
    state = _learning_state(step_index=2)
    result = schedule(state, Grade.AGAIN, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 0
    assert _seconds_until(NOW, result.due) == 60


def test_learning_hard_repeats_current_step():
    state = _learning_state(step_index=1)  # 10m step
    result = schedule(state, Grade.HARD, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 1
    assert _seconds_until(NOW, result.due) == 600


def test_learning_good_advances_one_step():
    state = _learning_state(step_index=1)  # 10m → next is 4h step
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 2
    assert _seconds_until(NOW, result.due) == 14400


def test_learning_good_past_last_step_graduates_to_review():
    state = _learning_state(step_index=3)  # 12h step is last
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.REVIEW
    assert result.stability == initial_stability(Grade.GOOD)
    assert result.difficulty == initial_difficulty(Grade.GOOD)
    # due = now + compute_interval(stability, 0.95)
    expected_interval_days = result.stability  # 0.95 retention: I ≈ S * factor; test directly
    # Concrete check: it should be at least several days, not minutes
    assert _seconds_until(NOW, result.due) > 86400


def test_learning_easy_graduates_immediately_from_any_step():
    for step in (0, 1, 2, 3):
        state = _learning_state(step_index=step)
        result = schedule(state, Grade.EASY, NOW)
        assert result.phase == Phase.REVIEW, f"step={step}"
        assert result.stability == initial_stability(Grade.EASY)
        assert result.difficulty == initial_difficulty(Grade.EASY)


def test_learning_grade_increments_reps_and_sets_last_review():
    state = _learning_state(step_index=0)
    result = schedule(state, Grade.GOOD, NOW)
    assert result.reps == 1
    assert result.last_review == NOW.isoformat()
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: 6 failures (no `schedule()` defined).

- [ ] **Step 3: Implement `schedule()` with LEARNING dispatch**

Append to `src/knowledge_base/code_review/scheduler.py`:

```python
# ---------------------------------------------------------------------------
# Scheduler entry point
# ---------------------------------------------------------------------------

def schedule(state: CardState, grade: Grade, now: datetime) -> ScheduleResult:
    """Compute the new state after grading.

    Pure function. Dispatches on state.phase.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if grade not in (Grade.AGAIN, Grade.HARD, Grade.GOOD, Grade.EASY):
        raise ValueError(f"unknown grade: {grade!r}")

    if state.phase == Phase.LEARNING:
        return _schedule_learning(state, grade, now)
    raise ValueError(f"unknown phase: {state.phase!r}")


def _graduate(grade: Grade, now: datetime, reps: int) -> ScheduleResult:
    """Promote a learning card to REVIEW with FSRS-seeded stability/difficulty."""
    stability = initial_stability(grade)
    difficulty = initial_difficulty(grade)
    interval = compute_interval(stability, desired_retention=DESIRED_RETENTION)
    due = (now + timedelta(days=interval)).isoformat()
    return ScheduleResult(
        phase=Phase.REVIEW,
        step_index=0,
        stability=stability,
        difficulty=difficulty,
        reps=reps + 1,
        last_review=now.isoformat(),
        due=due,
    )


def _schedule_learning(state: CardState, grade: Grade, now: datetime) -> ScheduleResult:
    if state.step_index < 0 or state.step_index >= len(LEARNING_STEPS_SEC):
        raise ValueError(f"learning step_index out of range: {state.step_index}")

    if grade == Grade.EASY:
        return _graduate(grade, now, state.reps)

    if grade == Grade.AGAIN:
        new_step = 0
    elif grade == Grade.HARD:
        new_step = state.step_index
    else:  # GOOD
        new_step = state.step_index + 1
        if new_step >= len(LEARNING_STEPS_SEC):
            return _graduate(grade, now, state.reps)

    due = (now + timedelta(seconds=LEARNING_STEPS_SEC[new_step])).isoformat()
    return ScheduleResult(
        phase=Phase.LEARNING,
        step_index=new_step,
        stability=0.0,
        difficulty=0.0,
        reps=state.reps + 1,
        last_review=now.isoformat(),
        due=due,
    )
```

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/scheduler.py tests/code_review/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat(code-review): LEARNING phase state transitions

Again resets to step 0 (1m); Hard repeats current step; Good advances or
graduates; Easy graduates immediately from any step. Graduation seeds
REVIEW-phase stability/difficulty via FSRS initial_*.
EOF
)"
```

---

## Task 4: REVIEW phase transitions

**Files:**
- Modify: `src/knowledge_base/code_review/scheduler.py`
- Modify: `tests/code_review/test_scheduler.py`

- [ ] **Step 1: Write failing tests for REVIEW transitions**

Append to `tests/code_review/test_scheduler.py`:

```python
from knowledge_base.srs.fsrs import (
    compute_retrievability,
    recall_stability,
    update_difficulty,
)


def _review_state(stability: float = 3.0, difficulty: float = 5.0,
                  last_review_iso: str | None = None, reps: int = 5) -> CardState:
    if last_review_iso is None:
        last_review_iso = (NOW - timedelta(days=2)).isoformat()
    return CardState(
        phase=Phase.REVIEW,
        step_index=0,
        stability=stability,
        difficulty=difficulty,
        reps=reps,
        last_review=last_review_iso,
        due=NOW.isoformat(),
    )


def test_review_good_uses_recall_stability_and_0_95_retention():
    state = _review_state(stability=3.0, difficulty=5.0,
                          last_review_iso=(NOW - timedelta(days=3)).isoformat())
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.REVIEW

    # Recompute the same math here to verify wiring (not asserting any specific number).
    elapsed = 3.0
    r = compute_retrievability(elapsed, 3.0)
    expected_s = recall_stability(3.0, 5.0, r, Grade.GOOD)
    assert result.stability == pytest.approx(expected_s, rel=1e-9)

    expected_d = update_difficulty(5.0, Grade.GOOD)
    assert result.difficulty == pytest.approx(expected_d, rel=1e-9)

    # Interval must use 0.95 retention, not the module default 0.9
    expected_interval = compute_interval(expected_s, desired_retention=0.95)
    expected_due = (NOW + timedelta(days=expected_interval)).isoformat()
    assert result.due == expected_due


def test_review_hard_produces_smaller_stability_than_good():
    state = _review_state(stability=10.0, difficulty=5.0,
                          last_review_iso=(NOW - timedelta(days=8)).isoformat())
    good_result = schedule(state, Grade.GOOD, NOW)
    hard_result = schedule(state, Grade.HARD, NOW)
    assert hard_result.stability < good_result.stability


def test_review_easy_produces_larger_stability_than_good():
    state = _review_state(stability=10.0, difficulty=5.0,
                          last_review_iso=(NOW - timedelta(days=8)).isoformat())
    good_result = schedule(state, Grade.GOOD, NOW)
    easy_result = schedule(state, Grade.EASY, NOW)
    assert easy_result.stability > good_result.stability


def test_review_grade_increments_reps():
    state = _review_state(reps=7)
    result = schedule(state, Grade.GOOD, NOW)
    assert result.reps == 8
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: 4 failures (REVIEW phase still raises "unknown phase").

- [ ] **Step 3: Implement `_schedule_review` for non-Again grades**

Add to `src/knowledge_base/code_review/scheduler.py`:

```python
def _schedule_review(state: CardState, grade: Grade, now: datetime) -> ScheduleResult:
    if state.last_review is None:
        raise ValueError("REVIEW-phase card must have last_review set")
    last_review = datetime.fromisoformat(state.last_review)
    if last_review.tzinfo is None:
        last_review = last_review.replace(tzinfo=timezone.utc)
    elapsed_days = max(0.0, (now - last_review).total_seconds() / 86400.0)

    if grade == Grade.AGAIN:
        # Handled in Task 5
        raise NotImplementedError("REVIEW Again handled in Task 5")

    from knowledge_base.srs.fsrs import compute_retrievability
    retrievability = compute_retrievability(elapsed_days, state.stability)
    new_stability = recall_stability(state.stability, state.difficulty, retrievability, grade)
    new_difficulty = update_difficulty(state.difficulty, grade)

    interval = compute_interval(new_stability, desired_retention=DESIRED_RETENTION)
    due = (now + timedelta(days=interval)).isoformat()
    return ScheduleResult(
        phase=Phase.REVIEW,
        step_index=0,
        stability=new_stability,
        difficulty=new_difficulty,
        reps=state.reps + 1,
        last_review=now.isoformat(),
        due=due,
    )
```

Update the dispatch in `schedule()`:

```python
    if state.phase == Phase.LEARNING:
        return _schedule_learning(state, grade, now)
    if state.phase == Phase.REVIEW:
        return _schedule_review(state, grade, now)
    raise ValueError(f"unknown phase: {state.phase!r}")
```

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: all tests PASS (REVIEW Again still raises NotImplementedError — no test exercises that path yet).

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/scheduler.py tests/code_review/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat(code-review): REVIEW-phase grading via FSRS math

Hard/Good/Easy invoke recall_stability + update_difficulty from
srs/fsrs.py and schedule via compute_interval at 0.95 retention.
Again path stubbed (NotImplementedError) — implemented in next task.
EOF
)"
```

---

## Task 5: RELEARNING phase + REVIEW → RELEARNING lapse

**Files:**
- Modify: `src/knowledge_base/code_review/scheduler.py`
- Modify: `tests/code_review/test_scheduler.py`

- [ ] **Step 1: Write failing tests for lapse + RELEARNING transitions**

Append to `tests/code_review/test_scheduler.py`:

```python
from knowledge_base.srs.fsrs import lapse_stability


def _relearning_state(step_index: int = 0, stability: float = 2.0,
                      difficulty: float = 6.0) -> CardState:
    return CardState(
        phase=Phase.RELEARNING,
        step_index=step_index,
        stability=stability,
        difficulty=difficulty,
        reps=10,
        last_review=(NOW - timedelta(minutes=30)).isoformat(),
        due=NOW.isoformat(),
    )


def test_review_again_lapses_to_relearning_step_0_with_30m_delay():
    state = _review_state(stability=3.0, difficulty=5.0,
                          last_review_iso=(NOW - timedelta(days=4)).isoformat())
    result = schedule(state, Grade.AGAIN, NOW)
    assert result.phase == Phase.RELEARNING
    assert result.step_index == 0
    assert _seconds_until(NOW, result.due) == 1800

    # Stability stored on the card is the lapse_stability computed at lapse time
    elapsed = 4.0
    r = compute_retrievability(elapsed, 3.0)
    expected_s = lapse_stability(3.0, 5.0, r)
    assert result.stability == pytest.approx(expected_s, rel=1e-9)

    # Difficulty updates immediately at lapse via update_difficulty(_, Again)
    expected_d = update_difficulty(5.0, Grade.AGAIN)
    assert result.difficulty == pytest.approx(expected_d, rel=1e-9)


def test_relearning_again_resets_to_step_0():
    state = _relearning_state(step_index=1)  # currently on 4h step
    result = schedule(state, Grade.AGAIN, NOW)
    assert result.phase == Phase.RELEARNING
    assert result.step_index == 0
    assert _seconds_until(NOW, result.due) == 1800
    # Lapse-time stability preserved
    assert result.stability == state.stability
    assert result.difficulty == state.difficulty


def test_relearning_hard_repeats_current_step():
    state = _relearning_state(step_index=1)
    result = schedule(state, Grade.HARD, NOW)
    assert result.phase == Phase.RELEARNING
    assert result.step_index == 1
    assert _seconds_until(NOW, result.due) == 14400


def test_relearning_good_advances_one_step():
    state = _relearning_state(step_index=0)  # 30m → next is 4h
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.RELEARNING
    assert result.step_index == 1
    assert _seconds_until(NOW, result.due) == 14400


def test_relearning_good_past_last_step_returns_to_review_with_lapse_stability():
    state = _relearning_state(step_index=1, stability=2.5, difficulty=6.0)
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.REVIEW
    # Stability is the lapse-time value preserved on the card, NOT re-derived
    assert result.stability == 2.5
    assert result.difficulty == 6.0
    # Interval scheduled via compute_interval at 0.95
    expected_interval = compute_interval(2.5, desired_retention=0.95)
    expected_due = (NOW + timedelta(days=expected_interval)).isoformat()
    assert result.due == expected_due


def test_relearning_easy_returns_to_review_immediately():
    state = _relearning_state(step_index=0, stability=2.5, difficulty=6.0)
    result = schedule(state, Grade.EASY, NOW)
    assert result.phase == Phase.REVIEW
    assert result.stability == 2.5
    assert result.difficulty == 6.0


def test_full_lapse_roundtrip_preserves_lapse_stability():
    """REVIEW → Again → RELEARNING → Good → Good → REVIEW with stability set at lapse."""
    s0 = _review_state(stability=4.0, difficulty=5.5,
                       last_review_iso=(NOW - timedelta(days=5)).isoformat())
    t1 = NOW
    after_lapse = schedule(s0, Grade.AGAIN, t1)
    s1 = CardState(
        phase=after_lapse.phase, step_index=after_lapse.step_index,
        stability=after_lapse.stability, difficulty=after_lapse.difficulty,
        reps=after_lapse.reps, last_review=after_lapse.last_review, due=after_lapse.due,
    )

    t2 = t1 + timedelta(minutes=30)
    after_good_1 = schedule(s1, Grade.GOOD, t2)
    assert after_good_1.phase == Phase.RELEARNING
    assert after_good_1.step_index == 1

    s2 = CardState(
        phase=after_good_1.phase, step_index=after_good_1.step_index,
        stability=after_good_1.stability, difficulty=after_good_1.difficulty,
        reps=after_good_1.reps, last_review=after_good_1.last_review, due=after_good_1.due,
    )

    t3 = t2 + timedelta(hours=4)
    after_good_2 = schedule(s2, Grade.GOOD, t3)
    assert after_good_2.phase == Phase.REVIEW
    # The stability that re-enters REVIEW is the lapse-time-computed value from step 1
    assert after_good_2.stability == after_lapse.stability
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: 7 failures (RELEARNING phase + REVIEW-Again not implemented).

- [ ] **Step 3: Implement `_schedule_relearning` and REVIEW Again path**

Update `_schedule_review` in `src/knowledge_base/code_review/scheduler.py` — replace the `if grade == Grade.AGAIN: raise NotImplementedError` block with:

```python
    if grade == Grade.AGAIN:
        from knowledge_base.srs.fsrs import compute_retrievability
        retrievability = compute_retrievability(elapsed_days, state.stability)
        lapse_s = lapse_stability(state.stability, state.difficulty, retrievability)
        new_difficulty = update_difficulty(state.difficulty, grade)
        due = (now + timedelta(seconds=RELEARNING_STEPS_SEC[0])).isoformat()
        return ScheduleResult(
            phase=Phase.RELEARNING,
            step_index=0,
            stability=lapse_s,
            difficulty=new_difficulty,
            reps=state.reps + 1,
            last_review=now.isoformat(),
            due=due,
        )
```

Add `_schedule_relearning` and wire dispatch:

```python
def _return_to_review(state: CardState, now: datetime) -> ScheduleResult:
    """Return to REVIEW from RELEARNING with the lapse-time stability/difficulty preserved."""
    interval = compute_interval(state.stability, desired_retention=DESIRED_RETENTION)
    due = (now + timedelta(days=interval)).isoformat()
    return ScheduleResult(
        phase=Phase.REVIEW,
        step_index=0,
        stability=state.stability,
        difficulty=state.difficulty,
        reps=state.reps + 1,
        last_review=now.isoformat(),
        due=due,
    )


def _schedule_relearning(state: CardState, grade: Grade, now: datetime) -> ScheduleResult:
    if state.step_index < 0 or state.step_index >= len(RELEARNING_STEPS_SEC):
        raise ValueError(f"relearning step_index out of range: {state.step_index}")

    if grade == Grade.EASY:
        return _return_to_review(state, now)

    if grade == Grade.AGAIN:
        new_step = 0
    elif grade == Grade.HARD:
        new_step = state.step_index
    else:  # GOOD
        new_step = state.step_index + 1
        if new_step >= len(RELEARNING_STEPS_SEC):
            return _return_to_review(state, now)

    due = (now + timedelta(seconds=RELEARNING_STEPS_SEC[new_step])).isoformat()
    return ScheduleResult(
        phase=Phase.RELEARNING,
        step_index=new_step,
        stability=state.stability,        # lapse-time value preserved
        difficulty=state.difficulty,
        reps=state.reps + 1,
        last_review=now.isoformat(),
        due=due,
    )
```

Update dispatch in `schedule()`:

```python
    if state.phase == Phase.LEARNING:
        return _schedule_learning(state, grade, now)
    if state.phase == Phase.REVIEW:
        return _schedule_review(state, grade, now)
    if state.phase == Phase.RELEARNING:
        return _schedule_relearning(state, grade, now)
    raise ValueError(f"unknown phase: {state.phase!r}")
```

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/scheduler.py tests/code_review/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat(code-review): RELEARNING phase + lapse handling

REVIEW Again → RELEARNING step 0, with lapse_stability stored on the card
and difficulty updated immediately. RELEARNING grades cycle the relearning
steps; Good past last step (or Easy) returns to REVIEW preserving the
lapse-time stability. Lapse round-trip test covers the full cycle.
EOF
)"
```

---

## Task 6: Scheduler edge cases (clock skew, invalid grade, learn-ahead helper)

**Files:**
- Modify: `src/knowledge_base/code_review/scheduler.py`
- Modify: `tests/code_review/test_scheduler.py`

- [ ] **Step 1: Write failing tests for edge cases**

Append to `tests/code_review/test_scheduler.py`:

```python
def test_clock_skew_floored_to_zero_elapsed():
    """If now < last_review, elapsed_days is clamped to 0 (no raise)."""
    future_last_review = (NOW + timedelta(hours=2)).isoformat()
    state = CardState(
        phase=Phase.REVIEW,
        step_index=0,
        stability=3.0,
        difficulty=5.0,
        reps=5,
        last_review=future_last_review,
        due=(NOW + timedelta(days=1)).isoformat(),
    )
    # Should not raise; the function should compute as if elapsed_days = 0.
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.REVIEW


def test_unknown_phase_raises():
    state = CardState(
        phase=99,  # type: ignore[arg-type]
        step_index=0, stability=0.0, difficulty=0.0,
        reps=0, last_review=None, due=NOW.isoformat(),
    )
    with pytest.raises(ValueError, match="unknown phase"):
        schedule(state, Grade.GOOD, NOW)


def test_unknown_grade_raises():
    state = _learning_state(step_index=0)
    with pytest.raises(ValueError, match="unknown grade"):
        schedule(state, 99, NOW)  # type: ignore[arg-type]


def test_learning_step_index_out_of_range_raises():
    state = _learning_state(step_index=4)
    with pytest.raises(ValueError, match="learning step_index out of range"):
        schedule(state, Grade.GOOD, NOW)


def test_relearning_step_index_out_of_range_raises():
    state = _relearning_state(step_index=2)
    with pytest.raises(ValueError, match="relearning step_index out of range"):
        schedule(state, Grade.GOOD, NOW)


def test_review_state_without_last_review_raises():
    state = CardState(
        phase=Phase.REVIEW, step_index=0,
        stability=3.0, difficulty=5.0, reps=1,
        last_review=None, due=NOW.isoformat(),
    )
    with pytest.raises(ValueError, match="last_review"):
        schedule(state, Grade.GOOD, NOW)


def test_due_within_learn_ahead_helper():
    """Helper used by DB layer to decide which learning cards to surface."""
    from knowledge_base.code_review.scheduler import is_due_within_learn_ahead
    in_window = (NOW + timedelta(minutes=15)).isoformat()
    out_of_window = (NOW + timedelta(minutes=30)).isoformat()
    past = (NOW - timedelta(minutes=5)).isoformat()
    assert is_due_within_learn_ahead(in_window, NOW) is True
    assert is_due_within_learn_ahead(out_of_window, NOW) is False
    assert is_due_within_learn_ahead(past, NOW) is True
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: 7 failures (clock skew not yet clamped — passes accidentally if `max(0.0, ...)` already there; if so move on; other tests fail because `is_due_within_learn_ahead` missing and step_index validation may not be present in REVIEW path).

- [ ] **Step 3: Add `is_due_within_learn_ahead` helper to `scheduler.py`**

```python
def is_due_within_learn_ahead(due_iso: str, now: datetime) -> bool:
    """True if a card's due time is past, or within LEARN_AHEAD_SEC of now."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    due = datetime.fromisoformat(due_iso)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return (due - now).total_seconds() <= LEARN_AHEAD_SEC
```

The `max(0.0, ...)` clamp in `_schedule_review` was already added in Task 4; verify it. The grade enum check and phase dispatch error are already present. If any of the validation tests still fail, add the missing checks where indicated.

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_scheduler.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/scheduler.py tests/code_review/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat(code-review): scheduler edge cases + learn-ahead helper

Clock-skew clamp, ValueError on bad phase/grade/step_index, missing
last_review check. New is_due_within_learn_ahead helper to be consumed
by the DB layer.
EOF
)"
```

---

## Task 7: DB schema migration (drop old `box` schema, recreate)

**Files:**
- Modify: `src/knowledge_base/code_review/db.py` (schema DDL + `init_db` migration)
- Modify: `tests/code_review/test_db.py`

- [ ] **Step 1: Write failing tests for the new schema and migration**

Replace the entire contents of `tests/code_review/test_db.py` with the version below (the old `box`-based tests are deleted along with the column they test):

```python
from datetime import datetime, timezone
import sqlite3 as _sqlite3

import pytest

from knowledge_base.code_review.db import (
    add_exercise,
    get_due_exercises,
    get_exercise_by_slug,
    init_db,
)


NOW_ISO = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    return init_db(tmp_path / "test.db")


def test_init_db_creates_tables(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "code_exercises" in tables
    assert "code_review_log" in tables


def test_new_schema_has_fsrs_columns(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert {"phase", "step_index", "stability", "difficulty"} <= cols
    assert "box" not in cols

    log_cols = {row[1] for row in conn.execute("PRAGMA table_info(code_review_log)").fetchall()}
    assert {"prior_phase", "new_phase", "prior_stability", "new_stability",
            "prior_difficulty", "new_difficulty"} <= log_cols
    assert "prior_box" not in log_cols
    assert "new_box" not in log_cols


def test_add_exercise_defaults_to_learning_phase(conn):
    eid = add_exercise(conn, "slug-a", "Title A", path="slug-a")
    ex = get_exercise_by_slug(conn, "slug-a")
    assert ex["phase"] == 1  # Phase.LEARNING
    assert ex["step_index"] == 0
    assert ex["stability"] == 0.0
    assert ex["difficulty"] == 0.0
    assert ex["reps"] == 0


def test_get_exercise_by_slug_missing_returns_none(conn):
    assert get_exercise_by_slug(conn, "no-such-slug") is None


def test_get_due_exercises_includes_null_due(conn):
    add_exercise(conn, "new-exercise", "New", path="new-exercise")
    due = get_due_exercises(conn, NOW_ISO)
    assert any(e["slug"] == "new-exercise" for e in due)


def test_get_due_exercises_excludes_future(conn):
    """Caller passes its own learn-ahead-adjusted timestamp; the DB just compares against `due`."""
    eid = add_exercise(conn, "future-ex", "Future", path="future-ex")
    # Manually set a far-future due
    conn.execute(
        "UPDATE code_exercises SET phase=2, due=? WHERE exercise_id=?",
        ("2099-01-01T00:00:00+00:00", eid),
    )
    conn.commit()
    due = get_due_exercises(conn, "2026-06-01T00:00:00+00:00")
    assert not any(e["slug"] == "future-ex" for e in due)


def test_migration_drops_old_box_schema(tmp_path):
    """A DB created with the legacy `box`-column schema is wiped on init_db."""
    from knowledge_base.code_review import db as db_mod

    db_path = tmp_path / "legacy.db"
    conn = _sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(
        """
        CREATE TABLE code_exercises (
            exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         TEXT    NOT NULL UNIQUE,
            title        TEXT    NOT NULL,
            path         TEXT    NOT NULL DEFAULT '',
            source       TEXT    NOT NULL DEFAULT '',
            box          INTEGER NOT NULL DEFAULT 1,
            last_review  TEXT,
            due          TEXT,
            reps         INTEGER NOT NULL DEFAULT 0,
            added        TEXT    NOT NULL
        );
        CREATE TABLE code_review_log (
            review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id  INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
            timestamp    TEXT    NOT NULL,
            grade        INTEGER NOT NULL,
            prior_box    INTEGER NOT NULL,
            new_box      INTEGER NOT NULL,
            elapsed_days REAL    NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO code_exercises (slug, title, path, added) "
        "VALUES (?, ?, ?, ?)",
        ("legacy-slug", "Legacy Title", "legacy-slug", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO code_review_log "
        "(exercise_id, timestamp, grade, prior_box, new_box, elapsed_days) "
        "VALUES (1, '2026-01-02T00:00:00+00:00', 3, 1, 2, 1.0)"
    )
    conn.commit()
    conn.close()

    migrated = db_mod.init_db(db_path)
    cols = {row[1] for row in migrated.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "phase" in cols
    assert "box" not in cols
    assert migrated.execute("SELECT COUNT(*) FROM code_exercises").fetchone()[0] == 0
    assert migrated.execute("SELECT COUNT(*) FROM code_review_log").fetchone()[0] == 0
    assert db_mod.LAST_MIGRATION_PURGE == ["legacy-slug"]


def test_init_db_fresh_no_migration_purge(tmp_path):
    from knowledge_base.code_review import db as db_mod
    db_mod.init_db(tmp_path / "fresh.db")
    assert db_mod.LAST_MIGRATION_PURGE == []
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_db.py -v
```

Expected: most tests fail — `phase`/`step_index` columns missing on the freshly-created table; migration test fails because old `box` column survives.

- [ ] **Step 3: Rewrite the DDL and `init_db` migration in `src/knowledge_base/code_review/db.py`**

Replace the `_DDL_EXERCISES`, `_DDL_REVIEW_LOG`, and `init_db` definitions with:

```python
_DDL_EXERCISES = """
CREATE TABLE IF NOT EXISTS code_exercises (
    exercise_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT    NOT NULL UNIQUE,
    title         TEXT    NOT NULL,
    path          TEXT    NOT NULL DEFAULT '',
    source        TEXT    NOT NULL DEFAULT '',
    phase         INTEGER NOT NULL DEFAULT 1,
    step_index    INTEGER NOT NULL DEFAULT 0,
    stability     REAL    NOT NULL DEFAULT 0.0,
    difficulty    REAL    NOT NULL DEFAULT 0.0,
    last_review   TEXT,
    due           TEXT,
    reps          INTEGER NOT NULL DEFAULT 0,
    added         TEXT    NOT NULL
);
"""

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS code_review_log (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id      INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
    timestamp        TEXT    NOT NULL,
    grade            INTEGER NOT NULL,
    prior_phase      INTEGER NOT NULL,
    new_phase        INTEGER NOT NULL,
    prior_stability  REAL    NOT NULL,
    new_stability    REAL    NOT NULL,
    prior_difficulty REAL    NOT NULL,
    new_difficulty   REAL    NOT NULL,
    elapsed_days     REAL    NOT NULL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_code_exercises_due  ON code_exercises (due);
CREATE INDEX IF NOT EXISTS idx_code_review_log_eid ON code_review_log (exercise_id);
"""

LAST_MIGRATION_PURGE: list[str] = []


def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    global LAST_MIGRATION_PURGE
    LAST_MIGRATION_PURGE = []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Detect old box-column schema and drop both tables if present
    with conn:
        existing_tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('code_exercises','code_review_log')"
            ).fetchall()
        }
        if "code_exercises" in existing_tables:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
            if "box" in cols:
                purged = [
                    row[0] for row in conn.execute(
                        "SELECT slug FROM code_exercises"
                    ).fetchall()
                ]
                conn.execute("DROP TABLE IF EXISTS code_review_log")
                conn.execute("DROP TABLE IF EXISTS code_exercises")
                LAST_MIGRATION_PURGE = purged

        conn.execute(_DDL_EXERCISES)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)

    return conn
```

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_db.py::test_init_db_creates_tables tests/code_review/test_db.py::test_new_schema_has_fsrs_columns tests/code_review/test_db.py::test_get_exercise_by_slug_missing_returns_none tests/code_review/test_db.py::test_migration_drops_old_box_schema tests/code_review/test_db.py::test_init_db_fresh_no_migration_purge -v
```

Expected: all 5 PASS. The other tests (referencing `add_exercise` / `get_due_exercises`) will still fail — those are addressed in Task 8.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/db.py tests/code_review/test_db.py
git commit -m "$(cat <<'EOF'
feat(code-review): rewrite DB schema for FSRS phases

Replace box column with phase/step_index/stability/difficulty. Review log
records prior/new stability/difficulty/phase. Migration from old box-schema
drops both tables; LAST_MIGRATION_PURGE records purged slugs for the TUI
to surface.
EOF
)"
```

---

## Task 8: DB CRUD updates (`add_exercise`, `get_due_exercises`, `record_grade`, `reset_*`)

**Files:**
- Modify: `src/knowledge_base/code_review/db.py`
- Modify: `tests/code_review/test_db.py`

- [ ] **Step 1: Write failing tests for new CRUD signatures**

Append to `tests/code_review/test_db.py`:

```python
from knowledge_base.code_review.db import record_grade, reset_exercise, reset_all_exercises, get_all_exercises


def _make_review_state(prior, new):
    """Build a record_grade payload from before/after dicts."""
    return {
        "exercise_id": prior["exercise_id"],
        "prior_phase": prior["phase"],
        "new_phase": new["phase"],
        "prior_stability": prior["stability"],
        "new_stability": new["stability"],
        "prior_difficulty": prior["difficulty"],
        "new_difficulty": new["difficulty"],
        "grade": 3,
        "elapsed_days": 1.0,
    }


def test_record_grade_writes_both_tables_atomically(conn):
    eid = add_exercise(conn, "rg", "RG", path="rg")
    prior = get_exercise_by_slug(conn, "rg")
    new = {
        "phase": 1, "step_index": 1, "stability": 0.0, "difficulty": 0.0,
        "reps": 1, "last_review": NOW_ISO, "due": "2026-01-01T00:10:00+00:00",
    }
    review = _make_review_state(prior, {**new, "phase": 1, "stability": 0.0, "difficulty": 0.0})
    record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    after = get_exercise_by_slug(conn, "rg")
    assert after["phase"] == 1
    assert after["step_index"] == 1
    assert after["due"] == "2026-01-01T00:10:00+00:00"
    assert after["last_review"] == NOW_ISO
    assert after["reps"] == 1

    logs = conn.execute("SELECT * FROM code_review_log WHERE exercise_id=?", (eid,)).fetchall()
    assert len(logs) == 1
    assert logs[0]["grade"] == 3


def test_record_grade_atomicity_on_bad_review_dict(conn):
    """A bad review payload rolls back both writes."""
    eid = add_exercise(conn, "atom", "Atom", path="atom")
    new = {
        "phase": 2, "step_index": 0, "stability": 3.0, "difficulty": 5.0,
        "reps": 1, "last_review": NOW_ISO, "due": "2026-01-04T00:00:00+00:00",
    }
    review = {"exercise_id": eid, "bogus_column": 1}
    with pytest.raises(ValueError):
        record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    after = get_exercise_by_slug(conn, "atom")
    # Should still be in initial state
    assert after["phase"] == 1
    assert after["reps"] == 0
    assert conn.execute("SELECT COUNT(*) FROM code_review_log").fetchone()[0] == 0


def test_reset_exercise_clears_state(conn):
    eid = add_exercise(conn, "rst", "Reset", path="rst")
    new = {
        "phase": 2, "step_index": 0, "stability": 5.0, "difficulty": 6.0,
        "reps": 3, "last_review": NOW_ISO, "due": "2026-02-01T00:00:00+00:00",
    }
    prior = get_exercise_by_slug(conn, "rst")
    review = _make_review_state(prior, new)
    record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    reset_exercise(conn, eid)
    after = get_exercise_by_slug(conn, "rst")
    assert after["phase"] == 1
    assert after["step_index"] == 0
    assert after["stability"] == 0.0
    assert after["difficulty"] == 0.0
    assert after["reps"] == 0
    assert after["last_review"] is None
    assert after["due"] is None


def test_reset_all_exercises_resets_every_row(conn):
    add_exercise(conn, "a", "A", path="a")
    add_exercise(conn, "b", "B", path="b")
    reset_all_exercises(conn)
    for ex in get_all_exercises(conn):
        assert ex["phase"] == 1
        assert ex["reps"] == 0
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_db.py -v
```

Expected: 4 new tests fail (`record_grade` signature changed, `reset_*` reset to box instead of phase).

- [ ] **Step 3: Update `src/knowledge_base/code_review/db.py`**

Remove `_REVIEW_LOG_COLS` definition referencing the old box columns and the old `update_exercise_scheduling` and `insert_review_log` functions. Replace with:

```python
_REVIEW_LOG_COLS = (
    "exercise_id", "timestamp", "grade",
    "prior_phase", "new_phase",
    "prior_stability", "new_stability",
    "prior_difficulty", "new_difficulty",
    "elapsed_days",
)


def record_grade(
    conn: sqlite3.Connection,
    exercise_id: int,
    new_state: dict,
    review: dict,
    now: str,
) -> None:
    """Update scheduling and insert review log atomically.

    new_state must contain: phase, step_index, stability, difficulty, reps,
    last_review, due. review must contain the keys listed in _REVIEW_LOG_COLS
    except `timestamp` (filled from `now`).
    """
    review_with_ts = {**review, "timestamp": now}
    unknown = set(review_with_ts) - set(_REVIEW_LOG_COLS)
    if unknown:
        raise ValueError(f"Unknown review_log columns: {unknown}")
    required = {"exercise_id", "grade", "prior_phase", "new_phase",
                "prior_stability", "new_stability",
                "prior_difficulty", "new_difficulty", "elapsed_days"}
    missing = required - set(review_with_ts)
    if missing:
        raise ValueError(f"Missing review_log columns: {missing}")

    cols = [c for c in _REVIEW_LOG_COLS if c in review_with_ts]
    with conn:
        conn.execute(
            "UPDATE code_exercises SET "
            "phase=?, step_index=?, stability=?, difficulty=?, "
            "last_review=?, due=?, reps=? "
            "WHERE exercise_id=?",
            (
                new_state["phase"], new_state["step_index"],
                new_state["stability"], new_state["difficulty"],
                new_state["last_review"], new_state["due"], new_state["reps"],
                exercise_id,
            ),
        )
        conn.execute(
            f"INSERT INTO code_review_log ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [review_with_ts[c] for c in cols],
        )
```

Replace `reset_exercise` and `reset_all_exercises`:

```python
def reset_exercise(conn: sqlite3.Connection, exercise_id: int) -> None:
    conn.execute(
        "UPDATE code_exercises SET "
        "phase=1, step_index=0, stability=0.0, difficulty=0.0, "
        "reps=0, last_review=NULL, due=NULL "
        "WHERE exercise_id=?",
        (exercise_id,),
    )
    conn.commit()


def reset_all_exercises(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE code_exercises SET "
        "phase=1, step_index=0, stability=0.0, difficulty=0.0, "
        "reps=0, last_review=NULL, due=NULL"
    )
    conn.commit()
```

`add_exercise`, `get_exercise_by_slug`, `get_due_exercises`, `get_all_exercises`, `discover_exercises`, `sync_exercises_from_disk`, `_extract_title` are unchanged. Delete `update_exercise_scheduling` and `insert_review_log` (no callers remain after the TUI is updated in Task 9).

- [ ] **Step 4: Run, confirm passing**

```bash
uv run pytest tests/code_review/test_db.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/db.py tests/code_review/test_db.py
git commit -m "$(cat <<'EOF'
feat(code-review): DB CRUD for FSRS state

record_grade takes new_state + review dicts and writes both tables in one
transaction. reset_* zero phase/step_index/stability/difficulty. Drop the
now-unused update_exercise_scheduling and insert_review_log helpers.
EOF
)"
```

---

## Task 9: TUI integration — grade flow, display, learn-ahead

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py`
- Modify: `tests/code_review/test_tui_grouping.py` (only fixture/label updates)
- Modify: `tests/code_review/test_massed_advance.py` (verify no break — massed mode unchanged)

- [ ] **Step 1: Inspect existing TUI test fixtures**

Run:

```bash
uv run pytest tests/code_review/test_tui_grouping.py tests/code_review/test_massed_advance.py -v --collect-only
```

Note any test that constructs exercise dicts directly — they will need `phase`/`step_index`/`stability`/`difficulty` keys instead of `box`. Grep:

```bash
grep -rn '"box"' tests/code_review/ src/knowledge_base/code_review/
```

For each match in tests, plan to swap `"box": N` → `"phase": 1, "step_index": 0, "stability": 0.0, "difficulty": 0.0`.

- [ ] **Step 2: Write failing test for new display formatter**

Create a new file `tests/code_review/test_tui_display.py`:

```python
from datetime import datetime, timedelta, timezone

from knowledge_base.code_review.tui import format_due_label


NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_format_due_label_minutes():
    due = (NOW + timedelta(minutes=8)).isoformat()
    assert format_due_label(due, NOW) == "due in 8m"


def test_format_due_label_hours():
    due = (NOW + timedelta(hours=3)).isoformat()
    assert format_due_label(due, NOW) == "due in 3h"


def test_format_due_label_days_returns_date():
    due = (NOW + timedelta(days=2)).isoformat()
    assert format_due_label(due, NOW) == "due 2026-05-20"


def test_format_due_label_overdue_shows_now():
    due = (NOW - timedelta(minutes=5)).isoformat()
    assert format_due_label(due, NOW) == "due now"


def test_format_due_label_null_returns_new():
    assert format_due_label(None, NOW) == "new"
```

- [ ] **Step 3: Run, confirm failure**

```bash
uv run pytest tests/code_review/test_tui_display.py -v
```

Expected: ImportError on `format_due_label`.

- [ ] **Step 4: Rewrite `src/knowledge_base/code_review/tui.py`**

Make the following changes:

**(a)** Replace the import line `from knowledge_base.code_review.leitner import schedule as leitner_schedule` with:

```python
from knowledge_base.code_review.scheduler import (
    LEARN_AHEAD_SEC,
    Phase,
    schedule as fsrs_schedule,
)
```

**(b)** Add a `format_due_label` helper near the top of the file (after the imports, before the existing `category_of`):

```python
def format_due_label(due_iso: str | None, now: datetime) -> str:
    """Render a card's due time relative to `now`.

    - None → "new"
    - past or now → "due now"
    - <1h ahead → "due in Xm"
    - <24h ahead → "due in Xh"
    - >=24h ahead → "due YYYY-MM-DD"
    """
    if due_iso is None:
        return "new"
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    due = datetime.fromisoformat(due_iso)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    delta_sec = (due - now).total_seconds()
    if delta_sec <= 0:
        return "due now"
    if delta_sec < 3600:
        return f"due in {int(delta_sec // 60)}m"
    if delta_sec < 86400:
        return f"due in {int(delta_sec // 3600)}h"
    return f"due {due.date().isoformat()}"


def _phase_label(phase: int) -> str:
    return {1: "learn", 2: "review", 3: "relearn"}.get(int(phase), "?")
```

**(c)** In `ExerciseListScreen._reload`, replace the body with:

```python
    def _reload(self) -> None:
        lv = self.query_one("#exercise-list", ListView)
        lv.clear()
        now = datetime.now(timezone.utc)
        as_of = (now + timedelta(seconds=LEARN_AHEAD_SEC)).isoformat()
        exercises = get_due_exercises(self._conn, as_of)
        if not exercises:
            # If there are learning cards beyond learn-ahead, surface when next one is due.
            from knowledge_base.code_review.db import get_all_exercises
            future = [
                e for e in get_all_exercises(self._conn)
                if e["due"] is not None and datetime.fromisoformat(e["due"]) > now + timedelta(seconds=LEARN_AHEAD_SEC)
            ]
            if future:
                future.sort(key=lambda e: e["due"])
                next_due = datetime.fromisoformat(future[0]["due"])
                minutes_out = max(1, int((next_due - now).total_seconds() // 60))
                lv.append(ListItem(Label(
                    f"No exercises due.  {len(future)} in learning, next due in {minutes_out}m.  m = massed   s = stats"
                )))
            else:
                lv.append(ListItem(Label("No exercises due.  m = massed practice   s = stats")))
        else:
            for ex in exercises:
                due_str = format_due_label(ex["due"], now)
                cat = category_of(ex)
                prefix = f"{cat} · " if cat else ""
                label = (
                    f"[{due_str}]  {prefix}{ex['slug']}  —  {ex['title']}  "
                    f"({_phase_label(ex['phase'])}, reps {ex['reps']})"
                )
                item = ListItem(Label(label))
                item._exercise = ex  # type: ignore[attr-defined]
                lv.append(item)
```

Note: `datetime` is already imported but `timedelta` may not be. Make sure the `from datetime import datetime, timedelta, timezone` line at the top includes `timedelta`.

**(d)** In `MassedBrowseScreen._render_list`, update the label construction:

```python
                marker = "[✓]" if ex["exercise_id"] in ids else "[ ]"
                due_str = format_due_label(ex["due"], datetime.now(timezone.utc))
                label = (
                    f"{marker} [{due_str}]  {ex['slug']}  —  {ex['title']}  "
                    f"({_phase_label(ex['phase'])}, reps {ex['reps']})"
                )
```

**(e)** In `StatsScreen._reload`, update the label:

```python
                due  = ex["due"][:10]         if ex["due"]         else "—"
                last = ex["last_review"][:10] if ex["last_review"] else "never"
                label = (
                    f"{_phase_label(ex['phase'])}  reps {ex['reps']:>3}  "
                    f"last {last}  next {due}    {ex['slug']}"
                )
```

**(f)** Replace `ReviewScreen.on_button_pressed` SRS branch (everything after the `if self._massed:` block):

```python
        # SRS mode
        grade_int = int(event.button.id.split("-")[1])  # "grade-1" → 1
        from knowledge_base.srs.fsrs import Grade
        grade = Grade(grade_int)
        now = datetime.now(timezone.utc)
        ex = self._exercise

        # Build prior CardState from the row
        from knowledge_base.code_review.scheduler import CardState
        prior = CardState(
            phase=Phase(ex["phase"]),
            step_index=ex["step_index"],
            stability=ex["stability"],
            difficulty=ex["difficulty"],
            reps=ex["reps"],
            last_review=ex["last_review"],
            due=ex["due"] or now.isoformat(),
        )
        result = fsrs_schedule(prior, grade, now)

        elapsed_days = 0.0
        if prior.last_review:
            lr = datetime.fromisoformat(prior.last_review)
            if lr.tzinfo is None:
                lr = lr.replace(tzinfo=timezone.utc)
            elapsed_days = max(0.0, (now - lr).total_seconds() / 86400.0)

        record_grade(
            self._conn,
            exercise_id=ex["exercise_id"],
            new_state={
                "phase": int(result.phase),
                "step_index": result.step_index,
                "stability": result.stability,
                "difficulty": result.difficulty,
                "reps": result.reps,
                "last_review": result.last_review,
                "due": result.due,
            },
            review={
                "exercise_id": ex["exercise_id"],
                "grade": grade_int,
                "prior_phase": int(prior.phase),
                "new_phase": int(result.phase),
                "prior_stability": prior.stability,
                "new_stability": result.stability,
                "prior_difficulty": prior.difficulty,
                "new_difficulty": result.difficulty,
                "elapsed_days": elapsed_days,
            },
            now=now.isoformat(),
        )
        self.app.pop_screen()
```

- [ ] **Step 5: Update `tests/code_review/test_tui_grouping.py` fixtures**

Open the file and replace every `"box": N` key in dict literals with `"phase": 1, "step_index": 0, "stability": 0.0, "difficulty": 0.0`. If the test asserts on the `box` label substring, change the assertion to look for the phase label (e.g., `"learn"` or `"review"`). Add `"step_index"`, `"stability"`, `"difficulty"` keys to any exercise dict that constructs one.

Use grep to find the spots:

```bash
grep -n '"box"\|box ' tests/code_review/test_tui_grouping.py tests/code_review/test_massed_advance.py
```

For each occurrence, replace with the new schema. Don't introduce phase changes that the tests don't actually exercise — defaults (`phase=1`, etc.) are fine.

- [ ] **Step 6: Run the affected TUI tests, confirm passing**

```bash
uv run pytest tests/code_review/test_tui_display.py tests/code_review/test_tui_grouping.py tests/code_review/test_massed_advance.py -v
```

Expected: all PASS.

- [ ] **Step 7: Run the full code_review test suite**

```bash
uv run pytest tests/code_review/ -v
```

Expected: all PASS. (`test_leitner.py` is still present and now fails on import — that's expected and will be deleted in Task 10. Until then, run with `--ignore`:)

```bash
uv run pytest tests/code_review/ -v --ignore=tests/code_review/test_leitner.py
```

- [ ] **Step 8: Manual smoke test the TUI**

```bash
uv run code-review
```

In a fresh terminal: open it, observe the migration banner ("Migrated DB — purged pre-migration rows: …"), pick an exercise, grade it Again, return to the list. Verify the card shows "due in 1m" or "due now" and reappears after waiting briefly. Quit with `q`.

Confirm the banner text mentions the 4 previously-Leitner slugs.

- [ ] **Step 9: Commit**

```bash
git add src/knowledge_base/code_review/tui.py tests/code_review/test_tui_display.py tests/code_review/test_tui_grouping.py tests/code_review/test_massed_advance.py
git commit -m "$(cat <<'EOF'
feat(code-review): TUI uses FSRS scheduler + sub-day due display

Grade callback builds a CardState, calls scheduler.schedule, persists via
record_grade. List screen displays "due in Xm/Xh" for sub-day timings and
"due YYYY-MM-DD" for longer. Empty-list footer surfaces when learning
cards exist beyond the 20m learn-ahead window. Stats/massed screens swap
"box N" labels for phase names.
EOF
)"
```

---

## Task 10: Delete `leitner.py`, update CLAUDE.md, final verification

**Files:**
- Delete: `src/knowledge_base/code_review/leitner.py`
- Delete: `tests/code_review/test_leitner.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Confirm nothing imports `leitner` anymore**

```bash
grep -rn 'leitner' src/ tests/ --include='*.py'
```

Expected: no matches. If anything remains, stop and fix it before deleting.

- [ ] **Step 2: Delete the files**

```bash
git rm src/knowledge_base/code_review/leitner.py tests/code_review/test_leitner.py
```

- [ ] **Step 3: Update `CLAUDE.md`**

In the "Source files (`code_review/`)" section, replace the bullet:

```
- `leitner.py` — 5-box Leitner scheduler; `schedule(current_box, grade, now) → LeitnerResult`; grade 1=Again/2=Hard/3=Good/4=Easy; intervals 1/2/4/8/16 days
```

with:

```
- `scheduler.py` — FSRS state machine for code exercises. Three phases: LEARNING (steps 1m/10m/4h/12h), REVIEW (FSRS-scheduled at 0.95 retention via `srs/fsrs.py`), RELEARNING (steps 30m/4h). `schedule(state, grade, now) → ScheduleResult` is the entry point; `initial_state(now)` returns a fresh card. 20m learn-ahead window matches Anki's `collapseTime`.
```

In the "Key Constraints — Code Review" section, replace the entire "### Leitner scheduling" subsection with:

```
### FSRS scheduling

- Three phases: LEARNING → REVIEW → RELEARNING. Pure state-machine in `scheduler.py`; FSRS math lives in `srs/fsrs.py`.
- Learning steps: `1m, 10m, 4h, 12h`. Relearning steps: `30m, 4h`. Desired retention: `0.95`. All hardcoded; edit `scheduler.py` to tune.
- Lapse (REVIEW → Again): stability is set to `lapse_stability(...)` computed at lapse time and preserved through relearning. On return to REVIEW, that stability schedules the next interval.
- Learn-ahead window of 20m means a card with a sub-day step shows up in the due list slightly early when the rest of the queue is clear.
```

In the "Quick Reference" section, no changes — `uv run code-review` still launches the TUI.

In the "Architecture" diagram, the `exercises/<slug>/` row at the bottom is unchanged.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest
```

Expected: all tests PASS. The leitner test file is gone so no `--ignore` needed.

- [ ] **Step 5: Manual smoke test (post-cleanup)**

```bash
uv run code-review
```

Verify nothing references Leitner in the UI. Step through one full review cycle (Again, then 1m later Good, see graduation banner-or-just-label switch from "learn" to "review").

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(code-review): remove Leitner, update docs

Deletes leitner.py and test_leitner.py. CLAUDE.md updated to describe the
FSRS state machine, learning/relearning steps, and lapse stability handling.
EOF
)"
```

---

## Self-review notes

- **Spec coverage:** All sections of the spec map to tasks. State machine → Tasks 2-6. DB schema/migration → Tasks 7-8. TUI display & flow → Task 9. CLAUDE.md update → Task 10. Testing requirements are embedded in each task's TDD steps. The `srs/fsrs.py` retention parameterization is Task 1.
- **Placeholder check:** None. Every code block is concrete.
- **Type consistency:** `CardState` and `ScheduleResult` have identical fields (phase, step_index, stability, difficulty, reps, last_review, due) — Task 2 defines them; Tasks 3-6 and 9 use them. `record_grade(conn, exercise_id, new_state, review, now)` signature is consistent between Task 8 (defined) and Task 9 (consumed). `Phase` enum (LEARNING=1, REVIEW=2, RELEARNING=3) consistent throughout. `format_due_label` and `_phase_label` defined in Task 9.
- **Open follow-ups (not blocking this plan):** `--prune` flag for orphaned DB rows (mentioned in spec as out of scope).
