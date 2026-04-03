# CLAUDE.md

## Project Overview

TUI-based memorization tool for drilling structured study material through progressive masking and type-in practice. Import markdown study notes or paste raw text, then drill through masking levels that build recall. A catalog TUI lets you browse and select material across multiple sources and topics.

A secondary calibration training system for confidence-interval estimation on real-world indicators is also included, though its practical usefulness is largely covered by Anki decks.

## Quick Reference

```bash
uv sync                              # install deps

# Generation review (primary feature)
uv run gen-import                       # import LOS JSON → data/srs.db
uv run gen-import-md <file> --deck D --topic T --source S  # import markdown
uv run gen-import-md <file> ... --preview  # preview parse without importing
uv run review-gen                       # launch catalog TUI (browse & select)
uv run review-gen [deck]                # launch with deck filter
uv run review-gen --stats               # stats screen only
uv run review-gen --limit N             # cap session size
uv run review-gen --practice 36         # massed practice: single reading (LOS)
uv run review-gen --practice 1-5        # massed practice: reading range (LOS)
uv run review-gen --practice 1,3,5      # massed practice: specific readings (LOS)
uv run review-gen --practice all        # massed practice: all readings (LOS)
uv run review-gen --ordered-practice 36   # ordered practice: single reading (LOS)
uv run review-gen --ordered-practice 1-5  # ordered practice: reading range (LOS)
uv run review-gen --ordered-practice 1,3,5 # ordered practice: specific readings (LOS)
uv run review-gen --ordered-practice all  # ordered practice: all readings (LOS)
uv run review-gen --source S --topic T --ordered-practice  # source-filtered practice
uv run review-gen --source S --section X --ordered-practice  # section-filtered practice
uv run review-gen --start-level 2       # start at max masking for familiar material
uv run review-gen --paste               # paste text for ephemeral drill
uv run review-gen --paste --save-as N --deck D --topic T --source S  # persist pasted text

# Calibration review (secondary feature)
uv run fetch-data <deck_key>         # fetch from World Bank API → data/<deck>/*.csv
uv run fetch-urban-data              # extract GHS-UCDB → data/urban_areas/*.csv
uv run fetch-desc-stats              # compute stats → data/descriptive_stats/*.csv
uv run srs-import --all              # import all calibration decks → data/srs.db
uv run review [deck_key]             # launch calibration TUI
uv run review --stats                # stats screen only

# Anki export (sharing/backup for calibration decks)
uv run build-deck <deck_key>         # generate .apkg from CSVs

uv run pytest                        # ~510 tests
```

Available calibration deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`, `education`, `governance`, `urban_areas`, `descriptive_stats`

## Architecture

```
# Generation review pipeline (primary)
markdown files ──→ gen-import-md ──→ data/srs.db ──→ review-gen TUI
cfa_level1_los.json ──→ gen-import ─┘                    │
                                                   catalog TUI (browse/select)

# Calibration review pipeline (secondary)
config.py (DECKS, ENTITIES)
    ↓
fetch-data / fetch-urban-data ──→ data/{deck}/*.csv
    ↓                                    ↓
srs-import ──→ data/srs.db ──→ review TUI    build-deck ──→ .apkg
```

### Generation review (`srs/`)
- `generation_db.py` — `generation_cards` and `generation_review_log` tables, CRUD, schema v2 (source/section_id/card_index)
- `generation_import.py` — JSON LOS data → SQLite card population
- `md_importer.py` — markdown parser (section-keyed + LOS-keyed formats) and `gen-import-md` CLI
- `catalog.py` — `CatalogNode` tree builder and `CatalogScreen` Textual widget for browsing/selecting material
- `generation_tui.py` — Textual TUI for generation card review, catalog entry point, paste-and-drill
- `masking.py` — letter-level masking algorithm (3 levels: 30%, 60%, first-letter-only)
- `text_scoring.py` — token-level Levenshtein comparison for feedback display
- `fsrs.py` — standard FSRS v6 scheduler (4-button: Again/Hard/Good/Easy), used for recall phase

### Calibration review (`srs/`)
- `scoring.py` — answer-normalized log-likelihood interval scoring; punitive point-prediction thresholds
- `scheduler.py` — continuous FSRS (v6-inspired): power-law forgetting curve, sigmoid recall/lapse blend, 23 tunable parameters
- `db.py` — SQLite schema (cards, review_log, schema_version), CRUD, migrations
- `importer.py` — CSV → SQLite card population, idempotent upsert preserving scheduling state
- `stats.py` — Brier score, calibration rate, score distribution, point prediction hit rate
- `tui.py` — Textual TUI for calibration review sessions and stats display

### Shared / data pipeline
- `config.py` — `DECKS` registry (indicators, era ranges, deck metadata per deck), shared `ENTITIES` (47), `URBAN_ENTITIES` (50 cities + aggregates)
- `card_gen.py` — pure functions for question/notes/answer/tag generation, shared by both `build_deck` and `srs/importer`
- `wb_api.py` — World Bank API client (no auth, `per_page=10000`)
- `ghsl.py` — GHS-UCDB GeoPackage reader (sqlite3, no auth)
- `fetch_data.py` — downloads World Bank data, selects best year per entity/era, writes one CSV per indicator
- `fetch_urban_data.py` — extracts GHS-UCDB data, computes median aggregates, writes CSVs
- `fetch_desc_stats.py` — computes descriptive statistics across entities per indicator
- `build_deck.py` — reads CSVs, generates questions/notes/tags, writes `.apkg` via genanki

## Adding a New Calibration Deck

1. Add a new entry to `DECKS` in `config.py` with: name, deck_id (unique int), output filename, data_dir, era_ranges, and indicators list
2. Each indicator needs: id, name, category, unit_label, wb_code, decimals, unit_prefix, time_invariant, current_only, has_regional_aggregates. Optional: `scale_factor` (int, default 1) — divides raw API values at build time for large absolute values (e.g., `1_000_000_000` for billions)
3. Create `data/<new_deck>/.gitkeep`
4. Run `uv run fetch-data <new_deck>` then `uv run srs-import <new_deck>` (and optionally `uv run build-deck <new_deck>` for Anki export)
5. Add the deck key to `WB_SOURCE_DECKS` in `fetch_desc_stats.py` (for descriptive stats generation)
6. New decks are automatically picked up by `srs-import --all`

## Key Constraints

### Generation cards (multi-source)
- **Multi-source hierarchy**: deck → topic (reading) → source (los/official/schweser/custom) → section → cards. Schema v2 unique key: `(deck, source, topic_id, section_id, card_index)`.
- **Catalog TUI**: default entry when running bare `review-gen`. Tree browser with multi-select at any level, launches massed or ordered practice.
- **Markdown import** (`gen-import-md`): parses section-keyed (`- 1.2: Title`) and LOS-keyed (`### LOS 1.a`) markdown into cards. Auto-detects format.
- **Paste-and-drill** (`--paste`): ephemeral text memorization. Sentence or line splitting. `--save-as` to persist.
- **Two review modes**: global review (masking → graduation → FSRS) and massed practice (transient, no DB writes)
- **Global review lifecycle**: generation phase (3 masking levels, queue-based spacing) → graduation (2 consecutive passes at max masking) → recall phase (standard FSRS v6 with Again/Hard/Good/Easy)
- **Massed practice** (`--practice`): in-memory only, no persistent state changes. Cards progress through masking levels → full type-in, then re-queue at end of deck. Filter by reading number(s).
- **Ordered practice** (`--ordered-practice`): like massed practice but cards cycle in fixed LOS order (ring buffer). Pass/fail affects masking level but not queue position — card always goes to back. User drills until they quit.
- **Start level** (`--start-level 0|1|2`): initial masking level for practice. Default 0 starts from easiest masking; 2 starts at max masking for familiar material.
- **Source-filtered practice**: `--source S --topic T --ordered-practice` drills cards from a specific source. Without `--source`, defaults to LOS cards for backwards compatibility.
- **Standard FSRS v6** (`fsrs.py`): completely independent from `scheduler.py`. Published default weights `W[0..18]`, 4-button discrete grading. Used only for recall phase.
- **Regression rule**: recall-phase cards that get Again with interval < 24h demote back to generation at level 2.
- **LOS data**: `data/cfa_level1_los.json` — 225 statements across 48 CFA Level I readings. Not gitignored (checked in).

### Calibration scoring
- **Answer-normalized log-likelihood**: interval scoring uses `S = -z²/2 - ln(CoV)` transformed via logistic (`center=2.0, scale=1.0`). No `indicator_std` parameter — depends only on interval bounds and true answer.
- **Point prediction scoring**: relative error `|guess - answer| / |answer|`. Thresholds: <5% perfect (1.0), <25% close (0.5), else miss (0.0). Near-zero fallback: when `|answer| < 1% of indicator_std`, uses absolute error normalized by `indicator_std` instead.
- **All values stored in display units** (divided by scale_factor). Scoring operates directly on stored values without conversion.

### Calibration scheduling (continuous FSRS)
- **Power-law forgetting curve** (FSRS v6): `R(t,S) = (1 + FACTOR*t/S)^DECAY` where `DECAY=-0.5`.
- **Continuous score → stability**: no binary lapse/success threshold. A sigmoid blend smoothly interpolates between recall and lapse stability formulas.
- **Desired retention is constant** (`R_d = 0.9`). Score affects intervals entirely through stability updates, not retention modulation.
- **Initial stability**: `S_0(s) = W_BASE * e^(W_SCALE * s)` where `W_BASE=0.0067` (~10 min at score=0), `W_SCALE=6.93` (~6.9 days at score=1.0).
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
