# CLAUDE.md

## Project Overview

Calibration training system for building base-rate knowledge of socioeconomic, financial, and development indicators. The primary interface is a TUI-based spaced repetition app with score-driven scheduling — calibration quality (confidence interval accuracy + precision) directly modulates review intervals via a simplified FSRS model.

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

uv run pytest                        # 194 tests
```

Available deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`, `urban_areas`, `descriptive_stats`

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
- `scoring.py` — Cobb-Douglas scoring (accuracy × precision geometric mean) with coverage gate; punitive point-prediction thresholds
- `scheduler.py` — simplified FSRS: DSR model with desired-retention modulation. Good scores lower the retention target → longer intervals
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
5. New decks are automatically picked up by `srs-import --all`

## Key Constraints

### SRS scoring
- **Retention modulation is inverted**: good score → *lower* desired retention → *longer* interval. The formula `R_d = 0.90 - 0.05*(score - 0.5)` produces range [0.875, 0.925]. This is because `interval = S * ln(R)/ln(0.9)` and lower R yields a larger ratio.
- **All values stored in display units** (divided by scale_factor). Scoring operates directly on stored values without conversion.
- **Two consecutive successes** (score >= 0.4) required for learning → review promotion.
- **Difficulty modifier** is off by default (`--difficulty-modifier` to enable).

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
- Development deck output is `knowledge_base.apkg` (not `knowledge_base_development.apkg`) for backward compatibility with existing Anki imports
