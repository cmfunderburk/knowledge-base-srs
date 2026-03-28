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
    exponent = -(raw_s - LOGISTIC_CENTER) / LOGISTIC_SCALE
    # Clamp exponent to avoid overflow; beyond ~709 exp() overflows in Python
    score = 1.0 / (1.0 + math.exp(min(exponent, 709.0)))
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
