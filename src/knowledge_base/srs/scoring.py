"""Scoring functions for SRS interval and point responses."""

import math
from dataclasses import dataclass

NORMAL_95_WIDTH = 3.92  # 2 * 1.96, width of 95% CI for standard normal
COVERAGE_PENALTY = 0.2  # multiplier when true answer is outside stated interval


@dataclass
class IntervalResult:
    accuracy_score: float
    precision_score: float
    covered: bool
    score: float


def score_interval(
    lower: float,
    upper: float,
    true_answer: float,
    indicator_std: float,
) -> IntervalResult:
    """Score a confidence interval response.

    Uses a Cobb-Douglas (geometric mean) combination of accuracy and precision.
    A coverage penalty of 0.2x is applied when the true answer falls outside
    the stated interval.

    Args:
        lower: Lower bound of the stated interval.
        upper: Upper bound of the stated interval.
        true_answer: The correct value.
        indicator_std: Standard deviation of the indicator distribution.

    Returns:
        IntervalResult with component scores and final score.
    """
    center = (lower + upper) / 2
    interval_width = upper - lower

    accuracy_score = math.exp(-abs(true_answer - center) / indicator_std)
    precision_score = math.exp(-interval_width / (NORMAL_95_WIDTH * indicator_std))

    core = accuracy_score ** 0.5 * precision_score ** 0.5
    covered = lower <= true_answer <= upper
    score = core if covered else core * COVERAGE_PENALTY

    return IntervalResult(
        accuracy_score=accuracy_score,
        precision_score=precision_score,
        covered=covered,
        score=score,
    )


def score_point(user_point: float, true_answer: float, indicator_std: float) -> float:
    """Score a single point-estimate response.

    Returns a discrete score based on how close the guess is relative to the
    indicator standard deviation.

    Args:
        user_point: The user's point estimate.
        true_answer: The correct value.
        indicator_std: Standard deviation of the indicator distribution.

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

    Args:
        score: Raw score to modify.
        true_answer: The correct value.
        indicator_mean: Mean of the indicator distribution.
        indicator_std: Standard deviation of the indicator distribution.

    Returns:
        Modified score, capped at 1.0.
    """
    difficulty_z = abs(true_answer - indicator_mean) / indicator_std
    modifier = 1 + 0.1 * difficulty_z
    return min(1.0, score * modifier)
