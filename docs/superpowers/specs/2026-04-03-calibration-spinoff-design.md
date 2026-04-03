# Calibration System Spin-Off Design

## Goal

Extract the calibration review system from `knowledge_base` into a standalone project at `/home/cmf/Dropbox/Apps/calibration`. Refocus `knowledge_base` as an initial-encoding aid (massed/ordered practice → Anki handoff).

## Context

The calibration system (confidence-interval estimation on real-world indicators) and the generation review system (progressive masking for text memorization) share a repo but have no code dependencies beyond the `data/srs.db` file (separate tables). The calibration system has its own scheduler (`scheduler.py`), scoring (`scoring.py`), card schema (`db.py`), TUI (`tui.py`), and data pipelines. Splitting them is clean.

## What Moves to `calibration/`

### Source modules (`src/knowledge_base/`)

- `config.py` — `DECKS` registry, `ENTITIES`, `URBAN_ENTITIES`
- `wb_api.py` — World Bank API client
- `ghsl.py` — GHS-UCDB GeoPackage reader
- `card_gen.py` — question/notes/answer generation
- `desc_stats.py` — descriptive statistics computation
- `fetch_data.py` — World Bank data download
- `fetch_urban_data.py` — GHS-UCDB data extraction
- `fetch_desc_stats.py` — descriptive stats pipeline
- `build_deck.py` — `.apkg` Anki export

### SRS modules (`src/knowledge_base/srs/`)

- `scoring.py` — interval/point scoring (log-likelihood, relative error)
- `scheduler.py` — continuous FSRS (23-param)
- `db.py` — calibration card schema/CRUD
- `importer.py` — CSV → calibration card import
- `stats.py` — Brier score, calibration rate, score distribution
- `tui.py` — calibration review TUI

### Tests

- `test_wb_api.py`
- `test_fetch_data.py`
- `test_ghsl.py`
- `test_fetch_urban_data.py`
- `test_desc_stats.py`
- `test_fetch_desc_stats.py`
- `test_build_deck.py`
- `test_card_gen.py`
- `test_config.py`
- `test_scoring.py`
- `test_scheduler.py`
- `test_srs_db.py`
- `test_importer.py`
- `test_stats.py`
- `test_integration.py`
- `test_srs_integration.py`

### Fixtures

- `tests/fixtures/` — all contents (`sample_gdp.csv`, `sample_urban.gpkg`, `create_urban_fixture.py`, `sample_srs_import/`)

### Data scaffolding

- `.gitkeep` directories for each calibration deck (`development/`, `tech_adoption/`, `conflict_security/`, `finance/`, `education/`, `governance/`, `urban_areas/`, `descriptive_stats/`)

## Calibration Project Structure

```
/home/cmf/Dropbox/Apps/calibration/
├── pyproject.toml
├── CLAUDE.md
├── .gitignore
├── src/
│   └── knowledge_base/          # preserved to avoid import rewrites
│       ├── __init__.py
│       ├── config.py
│       ├── wb_api.py
│       ├── ghsl.py
│       ├── card_gen.py
│       ├── desc_stats.py
│       ├── fetch_data.py
│       ├── fetch_urban_data.py
│       ├── fetch_desc_stats.py
│       ├── build_deck.py
│       └── srs/
│           ├── __init__.py
│           ├── scoring.py
│           ├── scheduler.py
│           ├── db.py
│           ├── importer.py
│           ├── stats.py
│           └── tui.py
├── tests/
│   ├── fixtures/
│   │   ├── sample_gdp.csv
│   │   ├── sample_urban.gpkg
│   │   ├── create_urban_fixture.py
│   │   └── sample_srs_import/
│   │       ├── gdp_pc_ppp.csv
│   │       └── desc_stats_gdp_pc_ppp.csv
│   ├── test_wb_api.py
│   ├── test_fetch_data.py
│   ├── test_ghsl.py
│   ├── test_fetch_urban_data.py
│   ├── test_desc_stats.py
│   ├── test_fetch_desc_stats.py
│   ├── test_build_deck.py
│   ├── test_card_gen.py
│   ├── test_config.py
│   ├── test_scoring.py
│   ├── test_scheduler.py
│   ├── test_srs_db.py
│   ├── test_importer.py
│   ├── test_stats.py
│   ├── test_integration.py
│   └── test_srs_integration.py
├── data/
│   ├── development/.gitkeep
│   ├── tech_adoption/.gitkeep
│   ├── conflict_security/.gitkeep
│   ├── finance/.gitkeep
│   ├── education/.gitkeep
│   ├── governance/.gitkeep
│   ├── urban_areas/.gitkeep
│   └── descriptive_stats/.gitkeep
└── resources/                   # .gitignore'd; large datasets (GHS-UCDB)
```

### `pyproject.toml`

- Name: `calibration`
- Same deps: `genanki`, `httpx`, `polars`, `textual`
- Entry points: `fetch-data`, `fetch-urban-data`, `fetch-desc-stats`, `build-deck`, `review`, `srs-import`
- Build system: `hatchling`
- Python: `>=3.12`

### `CLAUDE.md`

Trimmed version of current `CLAUDE.md` covering only:
- Calibration review pipeline
- Scoring rules (interval and point)
- Scheduling design (continuous FSRS, 23 params)
- Deck registry and adding new decks
- Data sources and quirks
- Anki export constraints (model ID, GUID stability, templates)
- Code style (same conventions)

### `.gitignore`

Based on current `.gitignore`, covering `data/*.db`, `data/**/*.csv`, `resources/`, `*.apkg`, etc.

### Zero import changes

The package is `knowledge_base` in both projects. All internal imports (`from knowledge_base.srs.scoring import ...`, `from knowledge_base.config import DECKS`) work without modification.

## Cleanup of `knowledge_base/`

### Remove source modules from `src/knowledge_base/`

- `config.py`, `wb_api.py`, `ghsl.py`, `card_gen.py`, `desc_stats.py`
- `fetch_data.py`, `fetch_urban_data.py`, `fetch_desc_stats.py`, `build_deck.py`

### Remove SRS modules from `src/knowledge_base/srs/`

- `scoring.py`, `scheduler.py`, `db.py`, `importer.py`, `stats.py`, `tui.py`

### Remove tests

All 16 calibration test files listed above.

### Remove fixtures

`tests/fixtures/` directory entirely.

### Remove entry points from `pyproject.toml`

- `fetch-data`, `fetch-urban-data`, `fetch-desc-stats`, `build-deck`, `review`, `srs-import`

### Keep entry points

- `review-gen`, `gen-import`, `gen-import-md`

### Remove unused dependencies

- `httpx` — only used by World Bank API client
- `polars` — only used by CSV processing pipelines

### Keep dependencies

- `genanki` — needed for future Anki export from generation cards
- `textual` — generation TUI

### Update `CLAUDE.md`

- Remove: calibration pipeline, scoring/scheduling docs, deck registry, data source quirks, Anki export details, `DECKS`/`ENTITIES` references
- Reframe: project description as initial-encoding aid (massed/ordered practice → Anki handoff)
- Keep: generation review pipeline, masking system, catalog, markdown import, massed/ordered practice docs, FSRS v6 (recall phase), code style

### Data directory cleanup

- Remove calibration deck `.gitkeep` directories
- Keep `data/srs.db` (generation tables) and `data/cfa_level1_los.json`
- Calibration tables in `srs.db` become dead weight but are harmless

## Database

No migration. Each project generates its own `data/srs.db`:
- `calibration/`: `srs-import` creates calibration tables (`cards`, `review_log`, `schema_version`)
- `knowledge_base/`: `gen-import` / `gen-import-md` creates generation tables (`generation_cards`, `generation_review_log`)

The leftover calibration tables in `knowledge_base/data/srs.db` are inert — `generation_db.py` never references them.

## Git History

Clean break. Files are copied (not `git subtree split`). The calibration project gets `git init` fresh. Full history remains in the `knowledge_base` repo for reference.

## Future Note

After this spin-off, the `knowledge_base` project will be extended with:
- New "exact-answer" card type for numerical/factual Q&A
- Revised massed practice reshuffling (positional spacing: fail → after next card; pass → 3/6/9/... cards back)
- Running pass counter on review screen
- Anki `.apkg` export for cards that reach 3+ passes

These are out of scope for this spec and will be designed separately.
