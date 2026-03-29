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
