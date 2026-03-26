"""Compute descriptive statistics over a polars DataFrame of entity values."""

from __future__ import annotations

import polars as pl


def compute_desc_stats(df: pl.DataFrame) -> dict:
    """Compute mean, median, std, min, max over 'value' column.

    Args:
        df: Must have columns 'entity' and 'value'.

    Returns:
        Dict with keys: n, mean, median, std, min_value, min_entity,
        max_value, max_entity.
    """
    values = df["value"]
    n = len(values)

    mean = values.mean()
    median = values.median()
    # Population std (ddof=0): the dataset is the full population of interest
    std = values.std(ddof=0) if n > 1 else 0.0

    min_idx = values.arg_min()
    max_idx = values.arg_max()

    return {
        "n": n,
        "mean": mean,
        "median": median,
        "std": std,
        "min_value": values[min_idx],
        "min_entity": df["entity"][min_idx],
        "max_value": values[max_idx],
        "max_entity": df["entity"][max_idx],
    }
