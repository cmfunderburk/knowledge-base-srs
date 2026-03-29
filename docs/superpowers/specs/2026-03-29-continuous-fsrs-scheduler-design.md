# Continuous FSRS Scheduler Design

**Date:** 2026-03-29
**Status:** Approved
**Branch:** `feat/scoring-scheduler-redesign`

## Problem

The current simplified FSRS scheduler uses a binary lapse/success threshold (`SUCCESS_THRESHOLD = 0.4`). Scores below 0.4 all produce nearly identical ~14 minute intervals regardless of whether the score is 0.0 or 0.35. This destroys the gradient information from the continuous scoring function, which produces a rich signal via answer-normalized log-likelihood.

## Approach

Replace the simplified DSR model with an FSRS v6-inspired scheduler that natively consumes continuous scores in [0,1]. Keep FSRS's validated structural insights (power-law forgetting curve, diminishing returns, spacing effect) but replace all discrete-grade formulas with continuous equivalents.

Key innovation: a sigmoid blend between recall and lapse stability updates, replacing the binary threshold. This produces a smooth, monotonically increasing interval-from-score curve across the entire [0,1] range.

## Design

### 1. Forgetting Curve (FSRS v6 power-law)

Replaces the current exponential `R = 0.9^(t/S)`.

```
decay   = -w[20]                    # default 0.5
factor  = 0.9^(1/decay) - 1

R(t, S) = (1 + factor * t/S) ^ decay
```

When `t = S`, `R = 0.9` by construction. The power-law curve drops faster initially but has a longer tail than exponential, better matching empirical forgetting data.

### 2. Interval Computation

```
I(S, R_d) = (S / factor) * (R_d^(1/decay) - 1)
```

When `R_d = 0.9`, simplifies to `I = S`. Desired retention is a constant `R_d = 0.9` (score affects intervals through stability updates, not retention modulation).

### 3. Initial Stability (First Review)

Replaces FSRS's 4-value lookup `S_0(G) = w[G-1]`.

```
S_0(s) = w_base * e^(w_scale * s)
```

Defaults: `w_base = 0.0067`, `w_scale = 6.93`.

Target curve (approximate):

| Score | Interval |
|-------|----------|
| 0.0   | ~10 min  |
| 0.2   | ~30 min  |
| 0.35  | ~1 hour  |
| 0.5   | ~5 hours |
| 0.7   | ~2 days  |
| 0.9   | ~4 days  |
| 1.0   | ~6 days  |

Single exponential is an approximation; the sharp knee around 0.4-0.5 in the ideal curve is smoothed out. Acceptable for initial testing; can be replaced with a two-segment function later if needed.

### 4. Initial Difficulty (First Review)

```
D_0(s) = w[4] - e^(w[5] * (s * 3)) + 1
```

Maps score [0,1] to FSRS's grade [1,4] range internally. Perfect first review starts the card easier; terrible first review starts it harder. Clamped to [1, 10].

### 5. Stability Update After Review (Established Cards)

For cards with `reps > 0`, stability is updated using a blend of recall and lapse formulas.

#### Recall stability

```
score_factor(s) = e^(w_sf * (s - anchor))

SInc = e^w[8] * (11 - D) * S^(-w[9]) * (e^(w[10] * (1-R)) - 1) * score_factor(s)

S_recall = S * (SInc + 1)
```

`SInc` (stability increase) is always >= 0, so `S_recall >= S` — successful recall never decreases stability.

Preserves three FSRS insights:
- `(11 - D)`: harder cards gain stability more slowly
- `S^(-w[9])`: diminishing returns on already-stable memories
- `(e^(w[10]*(1-R)) - 1)`: spacing effect (overdue reviews yield bigger gains)

`score_factor(s)` replaces discrete hard penalty / easy bonus with a continuous multiplier centered on `anchor`.

#### Lapse stability

```
S_lapse = w[11] * D^(-w[12]) * ((S+1)^w[13] - 1) * e^(w[14] * (1-R))
```

Directly from FSRS. Post-lapse stability is much smaller than pre-lapse, but higher previous stability yields somewhat higher post-lapse stability.

#### Blend

```
blend(s) = 1 / (1 + e^(-(s - blend_center) / blend_scale))

S_new = blend(s) * S_recall + (1 - blend(s)) * S_lapse
```

Defaults: `blend_center = 0.5`, `blend_scale = 0.08`.

| Score | Blend weight |
|-------|-------------|
| 0.0   | ~100% lapse |
| 0.2   | ~98% lapse  |
| 0.35  | ~88% lapse  |
| 0.5   | ~50/50      |
| 0.65  | ~97% recall |
| 0.7+  | ~99% recall |

This replaces the binary `SUCCESS_THRESHOLD = 0.4` split. Scores in the 0.3-0.6 range get meaningfully different stability updates.

### 6. Same-Day (Short-Term) Stability

For reviews where `elapsed_days < 1` (intra-session re-queued cards):

```
S_short = S * e^(w[17] * (s - anchor + w[18])) * S^(-w[19])
```

The `S^(-w[19])` convergence term (FSRS v6) prevents unbounded stability growth during rapid same-day reviews. For passing scores (`s >= blend_center`), the multiplier is floored at 1.0 so same-day reviews never decrease stability.

### 7. Difficulty Update

```
delta_D = -w[6] * (score - anchor)
D'     = D + delta_D * (10 - D) / 9
D_new  = w[7] * D_0(anchor) + (1 - w[7]) * D'
```

Clamped to [1, 10].

- **Delta**: score above anchor (0.7) decreases difficulty, below increases it
- **Linear damping** `(10 - D) / 9`: changes shrink as D approaches 10, preventing runaway
- **Mean reversion** `w[7] * D_0(anchor) + ...`: gentle pull toward neutral difficulty (w[7] is small, ~0.01)

The anchor at 0.7 means most reviews (any score below 0.7) push difficulty up. The system trends harder unless you consistently perform well. This is intentional for calibration training.

### 8. Parameters

| Parameter | Role | Default | Notes |
|-----------|------|---------|-------|
| `w_base` | Initial stability at score=0 | 0.0067 | ~10 min interval |
| `w_scale` | Initial stability growth rate | 6.93 | Exponential curve shape |
| `w[4]` | Base initial difficulty | 7.0 | FSRS range [1, 10] |
| `w[5]` | Initial difficulty curve shape | 0.5 | |
| `w[6]` | Difficulty update magnitude | 1.5 | |
| `w[7]` | Mean reversion weight | 0.01 | Small = gentle pull |
| `w[8]` | Recall stability gain (log-scale) | 1.5 | |
| `w[9]` | Stability diminishing returns | 0.15 | Higher = stronger diminishing returns |
| `w[10]` | Retrievability effect on recall gain | 1.0 | Higher = bigger spacing effect |
| `w[11]` | Post-lapse stability scaling | 1.5 | |
| `w[12]` | Difficulty effect on post-lapse | 0.1 | |
| `w[13]` | Pre-lapse S effect on post-lapse | 0.3 | |
| `w[14]` | Retrievability effect on post-lapse | 2.0 | |
| `w_sf` | Score factor scale (recall) | 2.0 | Continuous hard/easy multiplier |
| `w[17]` | Short-term stability rate | 0.5 | |
| `w[18]` | Short-term stability offset | 0.1 | |
| `w[19]` | Short-term convergence exponent | 0.07 | v6: prevents unbounded same-day growth |
| `w[20]` | Forgetting curve decay | 0.5 | v5-compatible default |
| `anchor` | Difficulty neutral point | 0.7 | Score at which difficulty is unchanged |
| `blend_center` | Recall/lapse blend midpoint | 0.5 | Score at which blend is 50/50 |
| `blend_scale` | Recall/lapse blend steepness | 0.08 | Smaller = sharper transition |
| `R_d` | Desired retention | 0.9 | Constant; score acts through stability |
| `INTRA_SESSION_THRESHOLD` | Re-queue cutoff (days) | 0.05 | ~1.2 hours |

All parameters are module-level constants in `scheduler.py`, documented with their role and rationale.

### 9. What Changes

**`scheduler.py`** — Full rewrite. New functions:
- `compute_retrievability(elapsed_days, stability)` — power-law
- `compute_interval(stability)` — uses constant R_d
- `initial_stability(score)` — exponential S_0
- `initial_difficulty(score)` — FSRS-adapted D_0
- `update_stability(stability, difficulty, retrievability, score)` — blend of recall/lapse
- `update_stability_short_term(stability, score)` — same-day formula
- `update_difficulty(difficulty, score)` — with mean reversion

**`tui.py`** — Update scheduling block in `on_input_submitted`:
- First review (`reps == 0`): use `initial_stability(score)`, `initial_difficulty(score)`
- Same-day review (`elapsed_days < 1`): use `update_stability_short_term()`
- Normal review: use `update_stability()`, `update_difficulty()`

**`db.py`** — Schema v3 migration:
- Update default difficulty from 0.3 to 7.0
- Update default stability from 0.5 to 0.0067
- Truncate `review_log` table

**`test_scheduler.py`** — Full rewrite for new functions.

**Unchanged:** `scoring.py`, `importer.py`, `stats.py`, `card_gen.py`, `config.py`

**Re-import workflow:** After implementation, run `srs-import --all` to reset all cards to new defaults. Review log is cleared by the migration.

### 10. What We're Dropping

From the current scheduler:
- `GROWTH_FACTOR` — replaced by FSRS recall stability formula
- `RETENTION_SCALE` — desired retention is now constant
- `SUCCESS_THRESHOLD` — replaced by continuous blend
- `LAPSE_FACTOR` — replaced by FSRS lapse stability formula
- `MIN_STABILITY` — FSRS formulas have natural floors
- `MIN_DIFFICULTY` / `MAX_DIFFICULTY` — replaced by FSRS range [1, 10]
- `INITIAL_STABILITY` — replaced by `initial_stability(score)`

### 11. Future Work

- **Parameter optimizer**: once sufficient review history accumulates, build an optimizer that fits parameters to actual forgetting data (analogous to FSRS's optimizer, adapted for continuous scores)
- **Initial stability curve**: if the single exponential proves too smooth, replace with a two-segment blend for sharper knee around s=0.4-0.5
- **Forgetting curve decay**: start with v5-compatible `w[20] = 0.5`; could train per-user later
