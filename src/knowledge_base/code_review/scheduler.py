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
