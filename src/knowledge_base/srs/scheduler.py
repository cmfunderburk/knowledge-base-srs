"""Simplified FSRS (DSR model) scheduler for spaced repetition reviews."""

import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROWTH_FACTOR = 2.0
BASE_RETENTION = 0.90
RETENTION_SCALE = 0.05
SUCCESS_THRESHOLD = 0.4
DIFFICULTY_RATE = 0.1
DIFFICULTY_ANCHOR = 0.7
MIN_DIFFICULTY = 0.05
MAX_DIFFICULTY = 1.0
LAPSE_FACTOR = 0.02
MIN_STABILITY = 0.01
MIN_INTERVAL = 0.01  # days (~15 minutes); allows sub-day intervals for lapsed cards
INITIAL_STABILITY = 0.5
INTRA_SESSION_THRESHOLD = 0.05  # days (~1.2 hours); below this, re-queue in-session


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_retrievability(elapsed_days: float, stability: float) -> float:
    """Return R = 0.9 ^ (elapsed_days / stability).

    Returns 0.0 if stability <= 0.
    """
    if stability <= 0:
        return 0.0
    return BASE_RETENTION ** (elapsed_days / stability)


def compute_desired_retention(score: float) -> float:
    """Return desired retention based on recent performance score.

    R_d = BASE_RETENTION - RETENTION_SCALE * (score - 0.5)

    Good scores lower the retention target → longer intervals (system trusts you).
    Bad scores raise it → shorter intervals (demands more practice).
    Range: [0.875, 0.925]
    """
    return BASE_RETENTION - RETENTION_SCALE * (score - 0.5)


def compute_interval(stability: float, desired_retention: float) -> float:
    """Return next review interval in days.

    interval = stability * (ln(desired_retention) / ln(0.9))
    Floored at MIN_INTERVAL (1.0).
    Returns MIN_INTERVAL if desired_retention <= 0 or >= 1.
    """
    if desired_retention <= 0 or desired_retention >= 1:
        return MIN_INTERVAL
    interval = stability * (math.log(desired_retention) / math.log(BASE_RETENTION))
    return max(MIN_INTERVAL, interval)


def update_difficulty(difficulty: float, score: float) -> float:
    """Update difficulty after a review.

    d_new = difficulty + DIFFICULTY_RATE * (DIFFICULTY_ANCHOR - score)
    Clamped to [MIN_DIFFICULTY, MAX_DIFFICULTY].
    """
    d_new = difficulty + DIFFICULTY_RATE * (DIFFICULTY_ANCHOR - score)
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d_new))


def update_stability(stability: float, difficulty: float, score: float) -> float:
    """Update memory stability after a review.

    Success (score >= SUCCESS_THRESHOLD):
        S_new = S * (1 + GROWTH_FACTOR * (1 - D) * score)
    Lapse (score < SUCCESS_THRESHOLD):
        S_new = max(MIN_STABILITY, S * LAPSE_FACTOR)
    """
    if score >= SUCCESS_THRESHOLD:
        return stability * (1 + GROWTH_FACTOR * (1 - difficulty) * score)
    else:
        return max(MIN_STABILITY, stability * LAPSE_FACTOR)
