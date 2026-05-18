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
    compute_retrievability,
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
    if state.phase == Phase.REVIEW:
        return _schedule_review(state, grade, now)
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
