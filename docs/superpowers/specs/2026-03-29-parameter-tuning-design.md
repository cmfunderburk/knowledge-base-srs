# Parameter Tuning System Design

**Date:** 2026-03-29
**Status:** Approved
**Branch:** `feat/scoring-scheduler-redesign`

## Problem

The continuous FSRS scheduler has 23 tunable parameters with hand-picked defaults. As review history accumulates, the forgetting curve and stability update parameters should be fit to actual performance data. Additionally, "feel" parameters (initial stability curve, difficulty anchor, blend center) need data-informed adjustment guidance.

## Approach

Two-part system:
1. **Core optimizer:** FSRS-style log-loss optimizer for forgetting curve parameters — replays review history, predicts retrievability, minimizes binary cross-entropy using scipy.
2. **Feel parameter analyzer:** Heuristic diagnostics that examine review patterns and suggest adjustments for parameters that require human judgment.

Single CLI entry point: `uv run srs-tune`.

## Design

### 1. Data Requirements

**Training signal:** Each review is binarized into recall (`score >= BLEND_CENTER`) or forget (`score < BLEND_CENTER`).

**Replay requirement:** The review_log stores raw scores and elapsed days, but not historical stability snapshots. The optimizer must replay each card's review history from initial state, recomputing stability at each step using candidate parameters.

**Data source:**
- `review_log` — timestamp, card_id, raw_score, elapsed_days
- `cards` — indicator_id, entity, era (for grouping), reps

**Minimum data:** 400 reviews (configurable via `--min-reviews`).

### 2. Core Optimizer

**Parameters optimized (11):**

| Parameter | Role | Bounds |
|-----------|------|--------|
| W8 | Recall stability gain (log-scale) | [0.0, 4.5] |
| W9 | Stability diminishing returns | [0.0, 0.8] |
| W10 | Retrievability effect on recall gain | [0.001, 3.5] |
| W11 | Post-lapse stability scaling | [0.001, 5.0] |
| W12 | Difficulty effect on post-lapse | [0.001, 0.25] |
| W13 | Pre-lapse S effect on post-lapse | [0.001, 0.9] |
| W14 | Retrievability effect on post-lapse | [0.0, 4.0] |
| W17 | Short-term stability rate | [0.0, 2.0] |
| W18 | Short-term stability offset | [0.0, 2.0] |
| W19 | Short-term convergence exponent | [0.0, 0.8] |
| DECAY | Forgetting curve decay (stored positive, used as -DECAY) | [0.1, 0.8] |

**Algorithm:**

1. Load all reviews from `review_log`, group by `card_id`, sort chronologically
2. For each card's review sequence, replay with candidate parameters:
   - First review: `initial_stability(score)`, `initial_difficulty(score)` (using current W_BASE/W_SCALE/W4/W5 — these are NOT being optimized)
   - Subsequent reviews: compute `retrievability = (1 + factor * elapsed/S)^(-decay)` using candidate DECAY, then update stability using candidate W8-W14 or W17-W19 (depending on elapsed time)
3. At each review, record predicted retrievability `R_hat` and actual outcome `y = 1 if score >= BLEND_CENTER else 0`
4. Compute binary cross-entropy loss: `L = -mean(y * ln(R_hat) + (1-y) * ln(1-R_hat))`
5. Minimize L using `scipy.optimize.minimize` with method L-BFGS-B and parameter bounds
6. FACTOR is rederived from DECAY at each evaluation: `factor = 0.9^(1/(-decay)) - 1`

**Output:** Optimized parameter values, before/after log-loss, number of reviews used.

### 3. Feel Parameter Analysis

Heuristic diagnostics — no optimization, just data-informed suggestions.

**W_BASE / W_SCALE (initial stability curve):**

Group first reviews (where the review is the card's first: determined by replaying and identifying the first entry per card) into score buckets (0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0). For each bucket, compute the interval that was assigned and the recall rate at the card's next review. If recall rate is consistently high (>85%), the initial interval was too short. If consistently low (<50%), too long.

Output: table of score bucket → interval given → next recall rate → directional suggestion.

**ANCHOR (difficulty neutral point):**

Compute the mean difficulty delta per review across all cards with 3+ reviews. If the average delta is positive, difficulty is trending upward (ANCHOR too high — most scores fall below it). If negative, ANCHOR too low.

Output: mean difficulty delta, current ANCHOR, suggested adjustment.

**BLEND_CENTER (recall/lapse boundary):**

For cards scored in the 0.3-0.7 range, bin by score (0.05 increments) and compute the fraction recalled on their next review. The empirical 50% recall crossover is the natural BLEND_CENTER — scores below it are more likely to be forgotten next time.

Output: score → next-review recall rate, empirical crossover point, suggested BLEND_CENTER.

**All suggestions are advisory.** The user decides whether to apply.

### 4. CLI Interface

Single entry point registered in `pyproject.toml` as `srs-tune`:

```
uv run srs-tune                    # full analysis + optimizer
uv run srs-tune --analyze-only     # skip optimizer, show diagnostics only
uv run srs-tune --dry-run          # show what would change, don't apply
uv run srs-tune --min-reviews N    # minimum reviews required (default 400)
uv run srs-tune --db PATH          # database path (default data/srs.db)
```

**Interactive confirmation:** After showing results, prompts "Apply optimized forgetting curve parameters? [y/N]". On confirmation, writes updated values to `scheduler.py`.

**Parameter application:** Reads `scheduler.py`, finds the constant definitions by pattern matching (e.g., `W8 = 1.5`), and replaces the values. Changes are visible in `git diff`.

### 5. File Structure

**New files:**
- `src/knowledge_base/srs/optimizer.py` — replay logic, loss computation, scipy minimize wrapper
- `src/knowledge_base/srs/analyze.py` — feel parameter diagnostics (initial stability calibration, difficulty trend, blend crossover)
- `src/knowledge_base/srs/tune.py` — CLI entry point, orchestrates optimizer + analysis + parameter writing
- `tests/test_optimizer.py` — optimizer unit tests (replay correctness, loss computation, parameter bounds)
- `tests/test_analyze.py` — analysis unit tests (bucket computation, trend calculation, crossover detection)

**Modified files:**
- `pyproject.toml` — add `scipy` dependency, add `srs-tune = "knowledge_base.srs.tune:main"` script entry point

### 6. What's NOT in Scope

- **Scoring function calibration:** Deferred until concrete cases of score miscalibration are documented from real usage.
- **W_BASE, W_SCALE, W4, W5, W6, W7 optimization:** These are not trained by the optimizer. W_BASE/W_SCALE get diagnostic suggestions; W4-W7 (difficulty dynamics) are left to manual tuning.
- **Automatic application:** The tool always requires confirmation before writing parameters. No cron/scheduled optimization.
- **Cross-validation or train/test split:** Not needed at this scale. The optimizer fits all available data. If overfitting becomes a concern (unlikely with 11 parameters and 400+ reviews), we can add regularization later.
