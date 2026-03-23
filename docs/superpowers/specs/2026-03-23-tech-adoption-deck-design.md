# Knowledge Base::Technology Adoption — Deck Design

## Overview

A second Anki with Uncertainty deck tracking technology adoption and diffusion indicators. Uses the same 47 entities as the development deck but with a different era structure: decade intervals from 1990 to present, capturing the internet boom and mobile revolution at higher temporal resolution than the development deck.

## Deck Registry Refactor

The codebase moves from a single hard-coded deck to a `DECKS` registry in `config.py`. Each deck defines its own indicators, era ranges, deck metadata, and data directory. `ENTITIES` remains shared across all decks.

```python
DECKS = {
    "development": {
        "name": "Knowledge Base::Global Development Indicators",
        "deck_id": 2026032300,
        "output": "knowledge_base.apkg",       # unchanged for backward compat
        "data_dir": "data/development",
        "era_ranges": { ... },   # existing 3 eras
        "indicators": [ ... ],   # existing 14 indicators
    },
    "tech_adoption": {
        "name": "Knowledge Base::Technology Adoption",
        "deck_id": 2026032301,
        "output": "knowledge_base_tech_adoption.apkg",
        "data_dir": "data/tech_adoption",
        "era_ranges": { ... },   # 4 eras
        "indicators": [ ... ],   # 6 indicators
    },
}
```

The development deck keeps `output: "knowledge_base.apkg"` for backward compatibility — users who have already imported it into Anki will get updates rather than a duplicate deck.

### CLI Changes

Entry points take a required positional deck key argument:

- `uv run fetch-data development`
- `uv run fetch-data tech_adoption`
- `uv run build-deck development`
- `uv run build-deck tech_adoption`

No argument prints available deck keys and exits.

### Data Directory Changes

Each deck's CSVs are isolated in their own subdirectory:

- `data/development/*.csv` (moved from `data/*.csv`)
- `data/tech_adoption/*.csv`

`.gitignore` updates from `data/*.csv` to `data/**/*.csv`.

### Code Changes

- **`config.py`**:
  - Current top-level `ERA_RANGES` and `INDICATORS` move into `DECKS["development"]`.
  - New `DECKS["tech_adoption"]` added with its 6 indicators and 4 eras.
  - `ENTITIES` and `REGIONS` stay top-level (shared across all decks).
  - Each indicator dict gets a `decimals` field (replaces the `ANSWER_DECIMALS` dict in `build_deck.py`) and a `unit_prefix` field (replaces the `UNIT_PREFIX` dict; default `""`; only `gdp_pc_ppp` uses `"$"`).

- **`fetch_data.py`**:
  - `main(deck_key)` looks up `DECKS[deck_key]` for indicators, era_ranges, and data_dir.
  - `select_best_year_for_era()` gets an `era_ranges` parameter instead of reading the module-level global.
  - `year_start` derived from the deck's era_ranges: `min(start for start, _, _ in era_ranges.values())`.
  - CLI wrapper uses `sys.argv[1]` to get deck key; prints available keys on missing/invalid argument.

- **`build_deck.py`**:
  - `main(deck_key)` constructs the deck from config: `genanki.Deck(deck_cfg["deck_id"], deck_cfg["name"])`.
  - `_INDICATOR_BY_ID` built per-invocation from `deck_cfg["indicators"]` (not a module-level global).
  - `ANSWER_DECIMALS` and `UNIT_PREFIX` dicts removed — replaced by `decimals` and `unit_prefix` fields on each indicator dict.
  - Dead module-level `DECK` constant removed.
  - CLI wrapper uses `sys.argv[1]` to get deck key.

- **`wb_api.py`**: Unchanged.

- **`pyproject.toml`**: Entry point functions stay the same (`fetch_data:main`, `build_deck:main`) but `main()` now reads `sys.argv[1]` for the deck key.

- **Tests**: Update imports — tests that reference `INDICATORS` or `ERA_RANGES` directly now access them via `DECKS["development"]`. `test_fetch_data.py` tests for `select_best_year_for_era` pass an explicit `era_ranges` dict.

### Migration Steps

1. Move existing `data/*.csv` → `data/development/`
2. Update `.gitignore` from `data/*.csv` to `data/**/*.csv`
3. Remove `data/.gitkeep`, add `data/development/.gitkeep` and `data/tech_adoption/.gitkeep`
4. Delete the orphaned `knowledge_base.apkg` in the repo root (gitignored, but clean up)

## Entity Selection

Same 47 entities as the development deck (7 regions, 15 major economies, 25 long-tail countries). Cards generated only where data exists — sparse countries simply have fewer cards.

## Era Ranges

| Era | Target | Acceptable Range | Rationale |
|-----|--------|------------------|-----------|
| 1990 | 1990 | 1988–1992 | Pre-internet baseline |
| 2000 | 2000 | 1998–2002 | Dot-com era, early broadband |
| 2010 | 2010 | 2008–2012 | Smartphone revolution, mobile-first |
| Current | Most recent | 2020–2026 | Present-day snapshot |

Decade intervals chosen to capture distinct technology adoption phases. Denser intervals (every 5 years) can be added later if needed.

## Indicators (6)

| id | name | category | unit_label | wb_code | decimals | has_regional_aggregates |
|----|------|----------|------------|---------|----------|------------------------|
| internet_users | Internet users | technology | % of population | IT.NET.USER.ZS | 1 | True |
| mobile_subscriptions | Mobile cellular subscriptions | technology | per 100 people | IT.CEL.SETS.P2 | 1 | True |
| broadband | Fixed broadband subscriptions | technology | per 100 people | IT.NET.BBND.P2 | 1 | True |
| rd_expenditure | R&D expenditure | technology | % of GDP | GB.XPD.RSDV.GD.ZS | 2 | True |
| hightech_exports | High-technology exports | technology | % of manufactured exports | TX.VAL.TECH.MF.ZS | 1 | True |
| electricity_access | Electricity access | technology | % of population | EG.ELC.ACCS.ZS | 1 | True |

All sourced from World Bank WDI. No new data sources required. None are time-invariant or current-only. No city population equivalent — no special-case handling needed.

### Data Availability Notes

- **Internet users**: Patchy in 1990 (most countries report 0 or null). Good from 2000.
- **Mobile subscriptions**: Available from 1990 for most countries. Values > 100 are common (multiple SIMs per person).
- **Broadband**: Essentially nonexistent in 1990. Starts ~2000 for developed countries, ~2005 for developing.
- **R&D expenditure**: Sparse — mostly OECD and major economies. Many long-tail countries will have gaps. Regional aggregates incomplete (Sub-Saharan Africa returns no data; Latin America and South Asia patchy).
- **High-tech exports**: Decent from 2000. Some countries report 0 or null.
- **Electricity access**: Good from 2000. Interesting variation in developing countries.

## Question Format

Same natural language format as the development deck, with explicit units:

```
What was India's Internet users in 2000, % of population?
```

```
What is South Korea's Mobile cellular subscriptions as of 2023, per 100 people?
```

## Notes Field

Same format: source + world avg + regional avg, with decimals matching the indicator's precision.

```
Source: World Bank WDI | World avg: 49.7, regional avg: 34.2
```

## Tag Schema

Same structure, with `category::technology`:

- `category::technology`
- `indicator::internet_users`, `indicator::mobile_subscriptions`, etc.
- `entity::india`, `entity_type::major`, etc.
- `era::1990`, `era::2000`, `era::2010`, `era::current`

## Card Count Estimate

47 entities × 6 indicators × 4 eras = 1,128 theoretical max.

After data gaps (R&D sparse for developing countries, broadband nonexistent pre-2000, internet sparse in 1990): **~700–900 cards.**

## Technical Details

- **Data source**: World Bank WDI API only (existing `wb_api.py` client)
- **GUID stability**: Same approach — Front field uniqueness ensures stable GUIDs across deck rebuilds.
- **Answer rounding**: Per-indicator decimals defined in indicator config (1 decimal for most, 2 for R&D expenditure).
- **Deck ID**: `2026032301` (distinct from development deck's `2026032300`).
