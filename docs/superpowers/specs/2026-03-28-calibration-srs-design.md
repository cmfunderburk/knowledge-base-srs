# Calibration SRS — Design Spec

A standalone spaced repetition module for calibration training, built as an integrated TUI within the knowledge-base project. Combines confidence interval estimation with SRS scheduling — the quality of your calibration directly modulates review spacing.

## Motivation

The existing Anki-with-Uncertainty workflow scores calibration quality but doesn't use that score to drive scheduling. The user manually presses Again/Hard/Good/Easy based on a recommendation. This module closes that loop: the scoring algorithm computes a score, that score modulates the desired retention parameter in a simplified FSRS model, and the resulting interval is applied automatically.

Additionally, Anki's architecture prevents score-driven scheduling without fragile monkey-patching (the scheduling states are computed before the user answers). Building a standalone SRS module sidesteps this entirely.

## Architecture

Integrated module at `src/knowledge_base/srs/`. Reads the same CSVs produced by the existing fetch pipeline. Shares `config.py` for indicator metadata. Maintains its own SQLite database for cards, scheduling state, and review history.

```
Existing pipeline (unchanged):
  fetch-data / fetch-urban-data / fetch-desc-stats → CSVs

New SRS module:
  srs-import → reads CSVs + descriptive stats → SQLite
  review     → TUI review session, reads/writes SQLite
```

### Module Structure

```
src/knowledge_base/
    card_gen.py     — shared question/notes/answer/tag generation (extracted from build_deck.py)

src/knowledge_base/srs/
    __init__.py
    db.py           — SQLite schema, card/review CRUD, schema migrations
    scheduler.py    — DSR model, interval computation, desired retention modulation
    scoring.py      — Accuracy/precision/coverage scoring, point prediction, Brier
    importer.py     — CSV → SQLite card population, idempotent upsert
    tui.py          — Textual app: review session, stats screen
    stats.py        — Brier score, calibration curve, per-indicator breakdowns
```

`card_gen.py` is extracted from `build_deck.py` as a prerequisite refactor. The functions `generate_question()`, `generate_notes()`, `format_answer()`, and `build_tags()` are pure (entity + indicator + year → strings) and used by both `build_deck.py` and `importer.py`.

### CLI Entry Points

- `uv run review [deck_key]` — launch review session (optional deck filter)
- `uv run review --stats` — stats screen only
- `uv run srs-import [deck_key]` — import/update cards from CSVs

### CSV Discovery

The importer follows the same conventions as `build_deck.py`. For a given deck key:

1. Look up `DECKS[key]` in `config.py` to get `data_dir` and `indicators` list
2. For each indicator, read `data/{data_dir}/{indicator_id}.csv`
3. For descriptive stats, read `data/descriptive_stats/{indicator_id}.csv` (or `urban_{indicator_id}.csv` for urban deck) to get `mean` and `std`
4. Match descriptive stats to cards by `indicator_id` and `year`

If no descriptive stats CSV exists for an indicator (e.g., a newly added indicator before `fetch-desc-stats` has been run), the importer warns and sets `indicator_mean` and `indicator_std` to NULL. Scoring falls back to a default SD computed from the card values in the import batch.

### Dependencies

- `textual` — TUI framework
- `sqlite3` (stdlib) — database

## Data Model

### Card Table

| Field | Type | Source |
|-------|------|--------|
| `card_id` | INTEGER PK | Auto-increment |
| `deck` | TEXT | Deck key (e.g., `development`) |
| `indicator_id` | TEXT | From config (e.g., `gdp_pc_ppp`) |
| `entity` | TEXT | Country/city name |
| `era` | TEXT | From source CSV era column: `current`, `1960`, `1990` for WB decks; actual year strings like `2000`, `2015` for urban deck |
| `question` | TEXT | Generated question text |
| `answer` | REAL | Numeric value in display units (divided by `scale_factor`) |
| `unit_prefix` | TEXT | `$`, `%`, etc. |
| `unit_label` | TEXT | Display context |
| `notes` | TEXT | World avg, regional avg, source |
| `tags` | TEXT | JSON array |
| `indicator_mean` | REAL | From descriptive stats CSV, in display units |
| `indicator_std` | REAL | From descriptive stats CSV, in display units |
| `scale_factor` | INTEGER | From config (used during import to convert raw → display) |
| `decimals` | INTEGER | From config |

Unique constraint on `(indicator_id, entity, era)` for idempotent import.

All numeric fields (`answer`, `indicator_mean`, `indicator_std`) are stored in display units — i.e., divided by `scale_factor`. This matches what the user types and sees, so the scoring algorithm operates directly on stored values without conversion. The importer applies `scale_factor` during import.

### Scheduling State (columns on card table)

| Field | Type | Description |
|-------|------|-------------|
| `difficulty` | REAL | D parameter, range [0.05, 1.0], default 0.3 |
| `stability` | REAL | S parameter (days), default 1.0 |
| `last_review` | TEXT | ISO timestamp |
| `due` | TEXT | ISO date |
| `reps` | INTEGER | Total review count, default 0 |
| `consecutive_successes` | INTEGER | For learning→review promotion, default 0 |
| `state` | TEXT | `new`, `learning`, `review` |

### Review Log (append-only)

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | INTEGER PK | Auto-increment |
| `card_id` | INTEGER FK | References card |
| `timestamp` | TEXT | ISO timestamp |
| `answer_mode` | TEXT | `interval` or `point` |
| `user_lower` | REAL | Lower bound (interval mode), NULL for point |
| `user_upper` | REAL | Upper bound (interval mode), NULL for point |
| `user_point` | REAL | Point estimate (point mode), NULL for interval |
| `true_answer` | REAL | The correct value |
| `raw_score` | REAL | Computed calibration score [0, 1] |
| `desired_retention` | REAL | The modulated retention target used |
| `interval_applied` | REAL | Days until next review |
| `elapsed_days` | REAL | Days since previous review |

### Schema Migration

`db.py` maintains a `schema_version` table with a single integer. On startup, `migrate()` checks the current version and applies any pending migrations sequentially. Migrations are defined as a list of SQL strings in `db.py`, indexed by version number. This is minimal but sufficient for a single-user SQLite database — no ORM or migration framework needed. The initial schema is version 1.

## Scoring Algorithm

### Interval Mode (95% CI)

Three components combined via Cobb-Douglas with coverage gate:

```
center = (lower + upper) / 2
interval_width = upper - lower

accuracy_score = exp(-|true_answer - center| / indicator_std)
precision_score = exp(-interval_width / (3.92 * indicator_std))

core = accuracy_score ^ 0.5 * precision_score ^ 0.5

if true_answer inside [lower, upper]:
    score = core
else:
    score = core * 0.2
```

The 3.92 constant is the width of a 95% CI for a normal distribution (~2 * 1.96 SDs).

**Accuracy** rewards centering your interval on the true answer. One SD off → 0.37, two SDs → 0.14.

**Precision** rewards tighter intervals. An interval spanning exactly 3.92 SDs → 0.37; tighter scores higher.

**Coverage gate** applies a 5x penalty when the true answer falls outside your interval. This reflects that missing your stated CI is a qualitatively different failure than imprecision.

The geometric mean (Cobb-Douglas) creates a nonlinear interaction: both accuracy and precision must be good for a high score. High accuracy with low precision (wide hedge) or high precision with low accuracy (confident but wrong) are both penalized more than a linear combination would suggest.

### Point Prediction Mode

The user claims certainty by entering a single number. Thresholds are deliberately punitive:

```
error = |true_answer - user_point| / indicator_std

if error < 0.05:  score = 1.0    # Within 0.05 SDs — you knew it
if error < 0.25:  score = 0.5    # Within 0.25 SDs — close but not certain-level
else:             score = 0.0    # Claimed certainty, was wrong
```

### Difficulty Modifier (toggleable)

Adjusts for question difficulty based on how far the true answer deviates from the cross-country mean:

```
difficulty_z = |true_answer - indicator_mean| / indicator_std
modifier = 1 + 0.1 * difficulty_z     # ~1.3 for 3-SD outliers
final_score = min(1.0, score * modifier)
```

Getting an outlier entity correct earns a small bonus. Disabled by default, toggleable in settings.

### Brier Score Tracking

For interval-mode reviews, a running Brier score on the coverage dimension:

```
brier_component = (0.95 - coverage_actual)^2
```

Where `coverage_actual` is 1 if truth was inside the interval, 0 otherwise. A well-calibrated reviewer at 95% should converge to ~0.0475. Feeds the stats screen, not scheduling.

## Scheduling (Simplified FSRS)

### DSR Model

Each card has Difficulty (D) and Stability (S). Retrievability (R) is computed on demand:

```
R = 0.9 ^ (elapsed_days / stability)
```

### Post-Review Updates

```
D_new = clamp(D + 0.1 * (0.7 - score), 0.05, 1.0)

if score >= 0.4:   # successful review
    S_new = S * (1 + growth_factor * (1 - D) * score)
else:              # lapse
    S_new = max(1.0, S * 0.3)
```

`growth_factor` is a fixed constant, initially 2.0. This becomes an optimizable parameter when upgrading to full FSRS.

### Desired Retention Modulation

The score shifts the target retention per-review:

```
base_retention = 0.90
retention = base_retention - 0.05 * (score - 0.5)   # range: [0.875, 0.925]
```

- Score 1.0 → 87.5% target → longer interval (system trusts you, accepts lower retention)
- Score 0.5 → 90% target → baseline interval
- Score 0.0 → 92.5% target → shorter interval (demands high retention, more practice)

Good scores *lower* the retention target, producing longer intervals — the system is more relaxed about retention for cards you've demonstrated knowledge of. Bad scores *raise* it, demanding more frequent review. The range is symmetric around baseline (±2.5%).

### Interval Computation

```
interval = stability * (ln(retention) / ln(0.9))
```

At 90% retention, interval equals stability. The retention shift scales it proportionally.

### Card States

- **New** → first review transitions to Learning
- **Learning** → two steps. Step 1: "show again this session" (intra-session repetition — the card re-enters the queue after other due cards, regardless of elapsed minutes). Step 2: due next day. Each successful review (score >= 0.4) increments `consecutive_successes`; a failure resets it to 0 and restarts at step 1. When `consecutive_successes` reaches 2, the card promotes to Review with initial stability of 1.0 day. If the user quits mid-session with a learning card at step 1, it remains at step 1 and appears first in the next session.
- **Review** → intervals computed by the DSR model

### Queue Priority

1. Learning cards at step 1 ("show again this session" — intra-session only)
2. Overdue Review-state cards (sorted by most overdue first)
3. Learning cards at step 2 (due date has passed)
4. New cards (configurable daily limit, default 20)

Session size is configurable (default: all due cards + new card limit). Can be overridden via `uv run review --limit N`.

## TUI Review Flow

### Question Screen

```
┌─────────────────────────────────────────────┐
│  Development > GDP per capita (PPP)   [3/47]│
│─────────────────────────────────────────────│
│                                             │
│  What is India's GDP per capita (PPP)       │
│  as of 2022, in 2021 international dollars? │
│                                             │
│  Answer: [_______________]                  │
│  Mode: 95% CI (tab to switch to Point)      │
│                                             │
└─────────────────────────────────────────────┘
```

### Answer Screen

```
┌─────────────────────────────────────────────┐
│  Development > GDP per capita (PPP)   [3/47]│
│─────────────────────────────────────────────│
│                                             │
│  Your interval: $1,000 – $5,000             │
│  True answer:   $2,389                      │
│  Status:        Within interval             │
│                                             │
│  Accuracy:  0.82  (center was $460 off)     │
│  Precision: 0.71  (width = 1.8 SD)         │
│  Coverage:  1.00                            │
│  Score:     0.74                            │
│                                             │
│  World avg: $18,463 | South Asia avg: $7,241│
│  Source: World Bank 2022                    │
│                                             │
│  Next review: 4.2 days                      │
│  [Enter] next  [s] stats  [q] quit          │
└─────────────────────────────────────────────┘
```

### Input Parsing

- `1000-5000` → interval mode (lower=1000, upper=5000)
- `-5--2` → interval mode with negatives
- `3200` → point prediction mode
- `Tab` toggles mode hint label

### Key Bindings

- `Enter` — submit answer / advance to next card
- `Tab` — toggle mode hint
- `q` — quit session (progress saved)
- `s` — stats screen
- `Ctrl+C` — quit (progress saved; each review committed on submit)

### Stats Screen

Accessible via `uv run review --stats` or `s` during session:

- Overall Brier score (running, last 30 days)
- Calibration curve: % of true answers inside stated 95% CIs
- Per-deck and per-indicator breakdown
- Score distribution histogram
- Cards due today / this week
- Point prediction hit rate

## Future Evolution

- **Full FSRS optimization**: Once sufficient review data exists, fit the 19 FSRS parameters to the user's actual review history. The simplified model's architecture (DSR + desired retention) is forward-compatible.
- **Web/mobile UI**: The `srs/` module has clean boundaries (db, scheduler, scoring are UI-independent). A web frontend (FastAPI + browser) or PWA could replace the TUI without touching the core logic.
- **`.apkg` export**: Lossy export for sharing decks via Anki (strips SRS state, keeps question/answer/tags).
- **Multi-user**: SQLite is single-user. A future Postgres migration would support multiple reviewers.

## What Stays Unchanged

The existing pipeline is untouched:

- `config.py` — shared, read-only from SRS perspective
- `fetch_data.py`, `fetch_urban_data.py`, `fetch_desc_stats.py` — data fetching
- `build_deck.py` — Anki `.apkg` generation
- All existing tests
