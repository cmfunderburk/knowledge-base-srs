"""Standard FSRS v6 scheduler with 4-button discrete grading.

Implements the published FSRS v6 algorithm. This module is completely
independent from scheduler.py (the continuous-score variant).

References:
  https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum


# ---------------------------------------------------------------------------
# Grade enum
# ---------------------------------------------------------------------------

class Grade(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


# ---------------------------------------------------------------------------
# Published FSRS v6 default weights
# ---------------------------------------------------------------------------

W: list[float] = [
    0.4072,   # W[0]  initial stability for Again
    1.1829,   # W[1]  initial stability for Hard
    3.1262,   # W[2]  initial stability for Good
    15.4722,  # W[3]  initial stability for Easy
    7.2102,   # W[4]  initial difficulty base
    0.5316,   # W[5]  initial difficulty curve
    1.0651,   # W[6]  difficulty update magnitude
    0.0589,   # W[7]  difficulty mean reversion weight
    1.5330,   # W[8]  recall stability gain (log-scale)
    0.1670,   # W[9]  stability diminishing returns exponent
    1.0458,   # W[10] retrievability effect on recall gain
    1.9552,   # W[11] post-lapse stability scaling
    0.1082,   # W[12] difficulty effect on post-lapse
    0.3264,   # W[13] pre-lapse stability effect
    2.1440,   # W[14] retrievability effect on post-lapse
    0.2854,   # W[15] Hard modifier for recall stability
    2.9898,   # W[16] Easy modifier for recall stability
    0.5116,   # W[17] short-term stability rate
    0.7004,   # W[18] short-term stability offset
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DECAY: float = -0.5
FACTOR: float = 0.9 ** (1 / DECAY) - 1    # derived so R(S, S) = 0.9
DESIRED_RETENTION: float = 0.9
MIN_DIFFICULTY: float = 1.0
MAX_DIFFICULTY: float = 10.0


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SchedulingResult:
    """Outcome of a single card scheduling computation."""
    difficulty: float
    stability: float
    interval: float          # days (float)
    due: str                 # ISO-8601 datetime string
    reps: int


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_retrievability(elapsed_days: float, stability: float) -> float:
    """Return retrievability R(t,S) = (1 + FACTOR*t/S)^DECAY.

    Returns 0.0 if stability <= 0.
    """
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def compute_interval(stability: float, desired_retention: float = DESIRED_RETENTION) -> float:
    """Return next review interval in days.

    I(S) = (S / FACTOR) * (R_d^(1/DECAY) - 1)

    With R_d = 0.9, this simplifies to I ≈ S.
    """
    return (stability / FACTOR) * (desired_retention ** (1 / DECAY) - 1)


def initial_stability(grade: Grade) -> float:
    """Return initial stability for a first review: S_0(G) = W[G-1]."""
    return W[int(grade) - 1]


def initial_difficulty(grade: Grade) -> float:
    """Return initial difficulty: D_0(G) = W[4] - e^(W[5]*(G-1)) + 1, clamped [1, 10]."""
    d = W[4] - math.exp(W[5] * (int(grade) - 1)) + 1
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d))


def recall_stability(
    stability: float,
    difficulty: float,
    retrievability: float,
    grade: Grade,
) -> float:
    """Return post-recall stability.

    S_r = S * (e^W[8] * (11-D) * S^(-W[9]) * (e^(W[10]*(1-R)) - 1) * modifier + 1)

    modifier = W[15] for Hard, W[16] for Easy, 1.0 for Good.
    """
    if grade == Grade.HARD:
        modifier = W[15]
    elif grade == Grade.EASY:
        modifier = W[16]
    else:
        modifier = 1.0

    s_inc = (
        math.exp(W[8])
        * (11 - difficulty)
        * stability ** (-W[9])
        * (math.exp(W[10] * (1 - retrievability)) - 1)
        * modifier
    )
    return stability * (max(s_inc, 0) + 1)


def lapse_stability(
    stability: float,
    difficulty: float,
    retrievability: float,
) -> float:
    """Return post-lapse stability.

    S_f = W[11] * D^(-W[12]) * ((S+1)^W[13] - 1) * e^(W[14]*(1-R))
    """
    return (
        W[11]
        * difficulty ** (-W[12])
        * ((stability + 1) ** W[13] - 1)
        * math.exp(W[14] * (1 - retrievability))
    )


def short_term_stability(stability: float, grade: Grade) -> float:
    """Return short-term (same-day) updated stability.

    S_s = S * e^(W[17] * (G - 3 + W[18]))
    """
    return stability * math.exp(W[17] * (int(grade) - 3 + W[18]))


def update_difficulty(difficulty: float, grade: Grade) -> float:
    """Update difficulty after a review.

    D' = D - W[6]*(G-3)
    D_new = W[7]*D_0(Good) + (1-W[7])*D', clamped [1, 10]
    """
    d_prime = difficulty - W[6] * (int(grade) - 3)
    d_0_good = initial_difficulty(Grade.GOOD)
    d_new = W[7] * d_0_good + (1 - W[7]) * d_prime
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d_new))


def schedule(
    difficulty: float,
    stability: float,
    reps: int,
    last_review: datetime | None,
    grade: Grade,
    now: datetime,
) -> SchedulingResult:
    """Compute full scheduling result for a card review.

    - reps=0: first review, uses initial_stability/initial_difficulty.
    - reps>0: compute elapsed_days and retrievability, apply recall or lapse
      stability. Same-day floor (elapsed < 1 day, grade != Again): apply
      max(new_stability, short_term_stability).

    Returns a SchedulingResult with difficulty, stability, interval (days),
    due (ISO-8601 str), and reps incremented by 1.
    """
    if reps == 0:
        new_stability = initial_stability(grade)
        new_difficulty = initial_difficulty(grade)
    else:
        if last_review is None:
            raise ValueError("last_review must be provided for reps > 0")

        # Normalise both datetimes to UTC-aware for safe subtraction
        if last_review.tzinfo is None:
            last_review = last_review.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        elapsed_days = (now - last_review).total_seconds() / 86400.0
        retrievability = compute_retrievability(elapsed_days, stability)

        if grade == Grade.AGAIN:
            new_stability = lapse_stability(stability, difficulty, retrievability)
        else:
            new_stability = recall_stability(stability, difficulty, retrievability, grade)

        # Same-day floor for passing grades
        if elapsed_days < 1.0 and grade != Grade.AGAIN:
            floor = short_term_stability(stability, grade)
            new_stability = max(new_stability, floor)

        new_difficulty = update_difficulty(difficulty, grade)

    interval = compute_interval(new_stability)
    due_dt = now + timedelta(days=interval)
    due_str = due_dt.isoformat()

    return SchedulingResult(
        difficulty=new_difficulty,
        stability=new_stability,
        interval=interval,
        due=due_str,
        reps=reps + 1,
    )
