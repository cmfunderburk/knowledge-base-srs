"""Pure statistical analysis functions for review history."""

from __future__ import annotations


def brier_score(coverages: list[bool], confidence: float = 0.95) -> float | None:
    """Compute the Brier score for a list of coverage outcomes.

    Each element indicates whether the true answer fell inside the stated
    confidence interval.  The Brier score is the mean squared error between
    the stated confidence and the binary outcome.

    Returns None for an empty list.
    Perfect calibration at 95% → ~0.0475.
    Always covered (100%) → ~0.0025.
    Never covered → ~0.9025.
    """
    if not coverages:
        return None
    n = len(coverages)
    total = sum((confidence - (1.0 if c else 0.0)) ** 2 for c in coverages)
    return total / n


def calibration_rate(coverages: list[bool]) -> float | None:
    """Return the fraction of intervals that covered the true answer.

    Returns None for an empty list.
    """
    if not coverages:
        return None
    return sum(coverages) / len(coverages)


def score_distribution(scores: list[float], bins: int = 10) -> list[dict]:
    """Bin a list of scores in [0, 1] into evenly-spaced buckets.

    Returns a list of dicts with keys 'lower', 'upper', 'count'.
    The last bin is inclusive on the upper bound so that score == 1.0 is
    counted.  The sum of all counts equals len(scores).

    Returns [] for an empty list.
    """
    if not scores:
        return []

    bin_width = 1.0 / bins
    result: list[dict] = []
    for i in range(bins):
        lower = i * bin_width
        upper = lower + bin_width
        if i < bins - 1:
            count = sum(1 for s in scores if lower <= s < upper)
        else:
            # Last bin: inclusive upper bound to capture score == 1.0
            count = sum(1 for s in scores if lower <= s <= upper)
        result.append({"lower": lower, "upper": upper, "count": count})
    return result


def point_hit_rate(scores: list[float]) -> dict | None:
    """Compute the fraction of scores that are perfect (1.0), partial (0.5),
    or miss (0.0).

    Returns None for an empty list.
    Returns {"perfect": float, "partial": float, "miss": float}.
    """
    if not scores:
        return None
    n = len(scores)
    perfect = sum(1 for s in scores if s == 1.0) / n
    partial = sum(1 for s in scores if s == 0.5) / n
    miss = sum(1 for s in scores if s == 0.0) / n
    return {"perfect": perfect, "partial": partial, "miss": miss}
