# CLAUDE.md

## Project Overview

Calibration training system for building base-rate knowledge of socioeconomic, financial, and development indicators. The primary interface is a TUI-based spaced repetition app with score-driven scheduling — interval scoring treats the user's response as an implied distributional forecast and uses the answer-normalized log-likelihood to modulate review intervals via a simplified FSRS model.

The system curates numerical data from World Bank, GHS Urban Centre Database, and other sources into reviewable flashcards. Users practice 95% confidence interval estimation or point predictions, building intuition for forecasting across domains relevant to GJOpen/Metaculus-style questions.

An Anki export pipeline (`build-deck`) is maintained for sharing and backup.

## Quick Reference

```bash
uv sync                              # install deps

# Data pipeline
uv run fetch-data <deck_key>         # fetch from World Bank API → data/<deck>/*.csv
uv run fetch-urban-data              # extract GHS-UCDB → data/urban_areas/*.csv
uv run fetch-desc-stats              # compute stats from WB API + urban CSVs → data/descriptive_stats/*.csv

# SRS review system
uv run srs-import --all              # import all decks → data/srs.db
uv run srs-import <deck_key>         # import a single deck
uv run review [deck_key]             # launch TUI review session
uv run review --stats                # stats screen only
uv run review --limit N              # cap session size
uv run review --difficulty-modifier  # enable outlier difficulty bonus

# Anki export (sharing/backup)
uv run build-deck <deck_key>         # generate .apkg from CSVs

uv run pytest                        # 218 tests
```

Available deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`, `education`, `governance`, `urban_areas`, `descriptive_stats`

## Architecture

Three-stage pipeline: `fetch` → CSVs → `srs-import` → SQLite → `review` TUI

```
config.py (DECKS registry, ENTITIES)
    ↓
fetch-data / fetch-urban-data / fetch-desc-stats → data/{deck}/*.csv
    ↓                                        ↓
srs-import → data/srs.db → review TUI    build-deck → .apkg (Anki export)
```

### Shared modules
- `config.py` — `DECKS` registry (indicators, era ranges, deck metadata per deck), shared `ENTITIES` (47), `URBAN_ENTITIES` (50 cities + aggregates)
- `card_gen.py` — pure functions for question/notes/answer/tag generation, shared by both `build_deck` and `srs/importer`
- `wb_api.py` — World Bank API client (no auth, `per_page=10000`)
- `ghsl.py` — GHS-UCDB GeoPackage reader (sqlite3, no auth)

### Data fetching
- `fetch_data.py` — downloads World Bank data, selects best year per entity/era, writes one CSV per indicator
- `fetch_urban_data.py` — extracts GHS-UCDB data, computes median aggregates, writes CSVs
- `fetch_desc_stats.py` — computes descriptive statistics (mean, median, SD, min, max) across entities per indicator
- `desc_stats.py` — `compute_desc_stats()` helper using population std (ddof=0)

### SRS module (`srs/`)
- `scoring.py` — answer-normalized log-likelihood interval scoring (`S = -z²/2 - ln(CoV)`, logistic transform); punitive point-prediction thresholds
- `scheduler.py` — continuous FSRS (v6-inspired): power-law forgetting curve, sigmoid recall/lapse blend, 23 tunable parameters. Score in [0,1] maps continuously to intervals via stability updates
- `db.py` — SQLite schema (cards, review_log, schema_version), CRUD, migrations
- `importer.py` — CSV → SQLite card population, idempotent upsert preserving scheduling state. Imports interval decks + descriptive stats (mean/median/SD as separate cards)
- `stats.py` — Brier score, calibration rate, score distribution, point prediction hit rate
- `tui.py` — Textual TUI for review sessions and stats display

### Anki export
- `build_deck.py` — reads CSVs, generates questions/notes/tags, writes `.apkg` via genanki

## Adding a New Deck

1. Add a new entry to `DECKS` in `config.py` with: name, deck_id (unique int), output filename, data_dir, era_ranges, and indicators list
2. Each indicator needs: id, name, category, unit_label, wb_code, decimals, unit_prefix, time_invariant, current_only, has_regional_aggregates. Optional: `scale_factor` (int, default 1) — divides raw API values at build time for large absolute values (e.g., `1_000_000_000` for billions)
3. Create `data/<new_deck>/.gitkeep`
4. Run `uv run fetch-data <new_deck>` then `uv run srs-import <new_deck>` (and optionally `uv run build-deck <new_deck>` for Anki export)
5. Add the deck key to `WB_SOURCE_DECKS` in `fetch_desc_stats.py` (for descriptive stats generation)
6. New decks are automatically picked up by `srs-import --all`

## Key Constraints

### SRS scoring
- **Answer-normalized log-likelihood**: interval scoring uses `S = -z²/2 - ln(CoV)` transformed via logistic (`center=2.0, scale=1.0`). No `indicator_std` parameter — depends only on interval bounds and true answer.
- **Point prediction scoring**: relative error `|guess - answer| / |answer|`. Thresholds: <5% perfect (1.0), <25% close (0.5), else miss (0.0). `indicator_std` parameter is accepted but unused for scoring (still needed by `apply_difficulty_modifier`).
- **All values stored in display units** (divided by scale_factor). Scoring operates directly on stored values without conversion.

### SRS scheduling (continuous FSRS)
- **Power-law forgetting curve** (FSRS v6): `R(t,S) = (1 + FACTOR*t/S)^DECAY` where `DECAY=-0.5`. Replaces exponential `R=0.9^(t/S)`.
- **Continuous score → stability**: no binary lapse/success threshold. A sigmoid blend (`BLEND_CENTER=0.5`, `BLEND_SCALE=0.08`) smoothly interpolates between recall and lapse stability formulas.
- **Desired retention is constant** (`R_d = 0.9`). Score affects intervals entirely through stability updates, not retention modulation.
- **Initial stability**: `S_0(s) = W_BASE * e^(W_SCALE * s)` where `W_BASE=0.0067` (~10 min at score=0), `W_SCALE=6.93` (~6.9 days at score=1.0).
- **Difficulty anchor**: `ANCHOR=0.7`. Scores below 0.7 increase difficulty, above decrease it. Difficulty range [1, 10] with FSRS mean reversion (`W7=0.01`).
- **Two-branch scheduling in TUI**: first review (`reps=0`) uses `initial_stability`/`initial_difficulty`; established cards always use full recall/lapse blend (same-day passing scores get a short-term floor to prevent stability decrease).
- **No state machine**: all cards use FSRS directly. No learning/review distinction.
- **New cards randomized**: `get_due_cards` returns new cards (reps=0) in random order for interleaved practice.
- **Intra-session repeat**: cards with computed interval < `INTRA_SESSION_THRESHOLD` (0.05 days) are re-queued within the session.
- **Difficulty modifier** is off by default (`--difficulty-modifier` to enable).
- **23 tunable parameters** in `scheduler.py` — all documented with role and rationale. See `docs/superpowers/specs/2026-03-29-continuous-fsrs-scheduler-design.md` for full spec.

### Anki export
- **Model ID `1677887272395`** must be reused — it's the Interval note type from the add-on
- **Card templates** (QFMT/AFMT in build_deck.py) contain Greenberg scoring JavaScript — do not modify the scoring algorithm
- **GUID stability** — genanki hashes the Front field. Rewording a question creates a new card, not an update

### Data sources
- **World Bank API quirks** — some indicators rebased (2021 PPP, $3.00/day poverty line). CO2 uses `EN.GHG.CO2.PC.CE.AR5` (old indicator deleted). Gini has no regional aggregates.

## Code Style

- Python 3.12+, managed with `uv`
- `polars` for CSV processing (not pandas)
- `textual` for TUI
- No type stubs or mypy — tests are the quality gate
- Tests use `pytest` with fixtures in `tests/fixtures/`

## Data

- CSVs in `data/` are gitignored — regenerated by `fetch-data` or `fetch-urban-data`
- `data/srs.db` is gitignored — personal review state, regenerated by `srs-import`
- `resources/` — gitignored; contains large public datasets (GHS-UCDB GeoPackage, etc.) that are fetched separately
- Anki deck outputs follow the pattern `knowledge_base_{deck_key}.apkg`
