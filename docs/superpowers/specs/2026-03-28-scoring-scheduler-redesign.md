# Scoring & Scheduler Redesign

## Problem

The current interval scoring normalizes accuracy and precision against the cross-entity indicator standard deviation. This produces inflated scores for wide intervals on high-variance indicators. Example: a [10, 20] interval on a true answer of 13.62 (US CO2 per capita) scores 0.777 because the indicator_std (~7.8) makes the 10-unit-wide interval look "tight" relative to global variance. In practice, [10, 20] represents imprecise knowledge ("it's a developed country") and should score much lower.

The learning/review state machine adds complexity without benefit once scoring is granular enough to drive scheduling directly.

## Design

### Scoring: Answer-normalized log-likelihood

The user's interval [L, U] implies a subjective normal distribution N(center, sigma_implied) where:

```
center      = (L + U) / 2
sigma_implied = (U - L) / 3.92        # 3.92 = 2 * 1.96 (95% CI width)
z           = |A - center| / sigma_implied
CoV         = sigma_implied / |A|
```

Raw score (answer-normalized log-likelihood, constant term dropped):

```
S = -z^2 / 2 - ln(CoV)
```

- `-z^2 / 2`: accuracy — how many implied-sigma is the truth from the stated center (Gaussian likelihood ratio)
- `-ln(CoV)`: precision — how tight is the interval relative to the answer scale

Transform to [0, 1] via logistic:

```
score = 1 / (1 + exp(-(S - LOGISTIC_CENTER) / LOGISTIC_SCALE))
```

Constants: `LOGISTIC_CENTER = 2.0`, `LOGISTIC_SCALE = 1.0`.

These were empirically calibrated so that scores align with the existing color thresholds (red < 0.4, yellow 0.4-0.7, green >= 0.7):

| Interval on A=13.62 | z    | CoV   | S    | score | label           |
|----------------------|------|-------|------|-------|-----------------|
| [10, 20]             | 0.54 | 0.187 | 1.53 | 0.39  | borderline bad  |
| [11, 16]             | 0.09 | 0.094 | 2.36 | 0.59  | OK              |
| [12, 15]             | 0.16 | 0.056 | 2.87 | 0.70  | borderline good |
| [13, 14.5]           | 0.34 | 0.028 | 3.52 | 0.82  | good            |
| [0, 30]              | 0.27 | 0.562 | 0.54 | 0.19  | bad             |

Coverage penalty emerges naturally from the z-score: if A is outside [L, U], then z > 1.96 and -z^2/2 < -1.92, which crushes the score without a discrete cliff. The separate `COVERAGE_PENALTY` multiplier is removed.

### IntervalResult changes

```python
@dataclass
class IntervalResult:
    z: float              # z-score: |A - center| / sigma_implied
    cov: float            # coefficient of variation: sigma_implied / |A|
    covered: bool         # whether A is in [L, U] (informational only)
    score: float          # logistic-transformed log-likelihood
```

`accuracy_score` and `precision_score` are removed. `z` and `cov` serve as diagnostics for TUI display.

### score_interval signature change

```python
def score_interval(lower: float, upper: float, true_answer: float) -> IntervalResult:
```

The `indicator_std` parameter is removed. The function depends only on the interval bounds and the true answer.

### Constants changes in scoring.py

Remove:
- `NORMAL_95_WIDTH = 3.92`
- `COVERAGE_PENALTY = 0.2`

Add:
- `CI_WIDTH_FACTOR = 3.92` (kept as a named constant for the 2 * 1.96 derivation)
- `LOGISTIC_CENTER = 2.0`
- `LOGISTIC_SCALE = 1.0`

### Edge cases

- **true_answer = 0**: CoV is undefined. Guard with `max(abs(true_answer), epsilon)` where epsilon is a small constant (e.g., 1e-9). In practice, all current indicators are strictly positive.
- **Very small width**: If `sigma_implied` approaches 0 while `center != true_answer`, z diverges to infinity and the score approaches 0 (correct: extreme overconfidence that's wrong should score near-zero). If `center == true_answer` exactly, z = 0/0; guard by returning score = 1.0 when both `sigma_implied < epsilon` and `abs(true_answer - center) < epsilon`.

### Unchanged

- `score_point` — still uses `indicator_std`, no changes
- `apply_difficulty_modifier` — still uses `indicator_mean` and `indicator_std`, no changes

### TUI display

Replace accuracy/precision lines with diagnostics:

```
Answer:     13.62
Your range: 10.00 - 20.00
Covered:    Yes

z-score:    0.54    CoV: 18.7%
Score:      0.385
```

`Covered` remains as informational feedback but is not a scoring input.

### Scheduler: eliminate state machine

Remove the `new`/`learning`/`review` state machine entirely. All cards use FSRS directly on every review.

**New constants:**
- `INITIAL_STABILITY = 0.5` — starting stability for new cards (0.5 days)
- `MIN_STABILITY`: change from 1.0 to 0.1 (so lapsed early cards come back in ~2.4 hours, not 1 day)

**Remove from scheduling logic:**
- `state` field and all state transitions
- `consecutive_successes` tracking
- Hardcoded 0-day / 1-day learning intervals
- 2-success promotion gate

**The review loop simplifies to:**

```python
new_difficulty = update_difficulty(old_difficulty, score)
new_stability = update_stability(old_stability, new_difficulty, score)
desired_ret = compute_desired_retention(score)
interval = compute_interval(new_stability, desired_ret)
```

No branching on state. Every card follows the same path.

### Database migration

Schema version bump. Changes to `cards` table:

- Remove `state` column (was: `new`, `learning`, `review`)
- Remove `consecutive_successes` column
- Default `stability` for new cards: `INITIAL_STABILITY` (0.5)
- Migration: any existing card with `stability < INITIAL_STABILITY` gets reset to `INITIAL_STABILITY`

### Card queue ordering

`get_due_cards` currently uses a state-based priority system (learning step-1 > overdue review > learning step-2 > new). With the state machine removed, the new ordering is:

1. **Overdue cards** (`due <= now` and `reps > 0`): ordered by `due ASC` (most overdue first)
2. **New cards** (`reps = 0`): presented in **random order** (interleaved practice — avoids mass-practicing a single indicator or category up front)

The random ordering for new cards is important: without it, cards are returned in insertion order which groups them by indicator/deck, defeating the calibration benefit of interleaved practice across diverse topics.

Implementation: `ORDER BY CASE WHEN reps > 0 THEN 0 ELSE 1 END, CASE WHEN reps > 0 THEN due END ASC, CASE WHEN reps = 0 THEN RANDOM() END`

### Intra-session repeat behavior

Currently, failed learning cards (interval = 0) are re-queued for intra-session repeat. Without the state machine, this behavior is driven by the interval value: if `compute_interval` returns a value below a threshold (e.g., < 0.05 days = ~1.2 hours), re-queue the card for intra-session repeat. The threshold aligns with the idea that sub-hour intervals should be handled within the current session rather than scheduling for later.

Constant: `INTRA_SESSION_THRESHOLD = 0.05` (days, ~1.2 hours).

### importer.py changes

New cards are initialized with:
- `stability = INITIAL_STABILITY` (0.5)
- `difficulty = 0.5` (unchanged)
- No `state` or `consecutive_successes` fields

### Files changed

| File | Changes |
|------|---------|
| `srs/scoring.py` | New formula, remove indicator_std param, new IntervalResult fields, new constants |
| `srs/scheduler.py` | MIN_STABILITY to 0.1, add INITIAL_STABILITY, add INTRA_SESSION_THRESHOLD |
| `srs/tui.py` | Remove state branching, update display, simplify review loop |
| `srs/db.py` | Schema migration: drop state/consecutive_successes columns; rewrite `get_due_cards` query (overdue first by due ASC, then new cards in random order) |
| `srs/importer.py` | Initialize new cards without state, with INITIAL_STABILITY |
| `tests/test_scoring.py` | Rewrite interval tests for new formula, remove indicator_std from test calls |
| `tests/test_scheduler.py` | Update `test_lapse_floors_at_one` for MIN_STABILITY=0.1, add INITIAL_STABILITY tests |
