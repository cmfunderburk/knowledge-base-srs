# Urban Areas Deck Design

## Overview

Add a new "Knowledge Base::Urban Areas" deck using the GHS Urban Centre Database (GHS-UCDB R2024A V1.1) from the EU Joint Research Centre. This is the first deck backed by a local static file (GeoPackage) rather than a web API.

**Source:** `resources/OECD/GHS_UCDB_GLOBE_R2024A_V1_1/GHS_UCDB_GLOBE_R2024A.gpkg`
**Entity set:** Top 50 urban centres by 2025 population
**Eras:** 1990, 2000, 2010, 2020, 2025 (explicit year labels, no "current" era)
**Expected cards:** ~1,242

## Data Source

The GHS-UCDB is a satellite-derived global urban centre database with 11,422 entries. Urban centre boundaries are defined consistently worldwide using the EU Degree of Urbanisation methodology (contiguous built-up areas with 50,000+ inhabitants). This solves the inconsistent metro/agglomeration boundary problem.

The data is stored in a GeoPackage (SQLite-based) with thematic tables: GHSL, SOCIOECONOMIC, EMISSIONS, CLIMATE, GREENNESS, HEALTH, INFRASTRUCTURE, etc. Column names have a BOM prefix (`\ufeff`).

## Entity Set

Top 50 cities by `GC_POP_TOT_2025`, ranging from Guangzhou (43.0M) to Nagoya (7.7M). Each city has:
- `uc_id`: GHS-UCDB integer ID (e.g., 5472 for Jakarta)
- `name`: Display name (e.g., "Jakarta")
- `country`: Country name from `GC_CNT_GAD_2025`
- `income_group`: World Bank Income Group from `GC_DEV_WIG_2025`
- `tag_slug`: Kebab-case slug for Anki tags

Synthetic aggregate entities for reference context on cards:
- "All Cities" — median across all 50 cities
- One per income group (High, Upper Middle, Lower Middle, Low)

Entity type: "city" for cities, "aggregate" for reference rows.

## Indicators

| ID | Name | GHS Table | Column Prefix | Unit | Decimals | Years | Scale |
|----|------|-----------|---------------|------|----------|-------|-------|
| `population` | Population | GHSL | `GH_POP_TOT` | millions | 1 | 1990-2025 | 1,000,000 |
| `co2_per_capita` | CO2 emissions per capita | EMISSIONS | `EM_CO2_PEC` | tonnes per person | 2 | 1990-2020 | 1 |
| `pm25_concentration` | PM2.5 concentration | EMISSIONS | `EM_PM2_CON` | ug/m3 | 1 | 2000-2020 | 1 |
| `life_expectancy` | Life expectancy | SOCIOECONOMIC | `SC_SEC_LET` | years | 1 | 1990-2020 | 1 |
| `built_up_per_capita` | Built-up area per capita | GHSL | `GH_BPC_TOT` | m2 per person | 1 | 1990-2025 | 1 |
| `hdi` | Human Development Index | SOCIOECONOMIC | `SC_SEC_HDI` | index (0-1) | 3 | 1990-2020 | 1 |

Notes:
- Taipei (Taiwan) is missing HDI and life expectancy (49/50 coverage for those indicators)
- PM2.5 starts at 2000 (no 1990 data)
- Only population and built-up per capita have 2025 data

## Architecture

### Pipeline

Same two-stage pattern as existing decks:

```
config.py (URBAN_ENTITIES + urban_areas deck)
    → fetch_urban_data.py (GeoPackage → per-indicator CSVs)
    → build_deck.py (CSVs → .apkg)
```

### New Files

**`src/knowledge_base/ghsl.py`** (~60 lines)

Thin GeoPackage reader. Opens the SQLite file, queries a thematic table for specified column prefix, UC_IDs, and years. Returns flat list of `{"uc_id": int, "year": int, "value": float}` dicts. Handles BOM prefix internally.

Single public function:
```python
def fetch_indicator(
    gpkg_path: Path,
    table_name: str,       # e.g., "EMISSIONS"
    column_prefix: str,    # e.g., "EM_CO2_PEC"
    uc_ids: list[int],
    years: list[int],
) -> list[dict]:
```

**`src/knowledge_base/fetch_urban_data.py`** (~100 lines)

Orchestrator analogous to `fetch_data.py`. For each indicator:
1. Calls `ghsl.fetch_indicator()` to extract data
2. Maps UC_IDs to entity names via `URBAN_ENTITIES`
3. Computes median aggregates: "All Cities" + per income group, per era
4. Writes CSV in standard format: `entity, entity_type, region, era, year, value, source`

CLI entry point: `fetch-urban-data` (no arguments needed — single deck).

### Modified Files

**`src/knowledge_base/config.py`**

Add `URBAN_ENTITIES` list and `DECKS["urban_areas"]` entry. The deck config includes:
- `entities` key pointing to `URBAN_ENTITIES` (deck-specific entity list)
- `reference_entity`: "All Cities" (replaces "World" for reference averages)
- `reference_entity_type`: "aggregate" (replaces "region")
- `gpkg_path`: path to GeoPackage file
- Standard fields: name, deck_id, output, data_dir, era_ranges, indicators

Indicator config shape for urban deck:
```python
{
    "id": "co2_per_capita",
    "name": "CO2 emissions per capita",
    "category": "emissions",
    "unit_label": "tonnes per person",
    "ghsl_table": "EMISSIONS",
    "ghsl_column": "EM_CO2_PEC",
    "decimals": 2,
    "unit_prefix": "",
    "years": [1990, 2000, 2010, 2020],
    "scale_factor": 1,
}
```

**`src/knowledge_base/build_deck.py`**

Two small generalizations:

1. `_find_entity_config`: use `deck_cfg.get("entities", ENTITIES)` for entity lookup
2. `compute_reference_averages`: use `deck_cfg.get("reference_entity", "World")` and `deck_cfg.get("reference_entity_type", "region")` instead of hardcoded values

No changes to question generation — all eras are historical ("What was...in {year}?").

**`pyproject.toml`**

Add entry point: `fetch-urban-data = "knowledge_base.fetch_urban_data:main"`

### CSV Format

Identical to existing decks:

```csv
entity,entity_type,region,era,year,value,source
Jakarta,city,Upper Middle,2020,2020,1.97,GHS-UCDB R2024A
All Cities,aggregate,,2020,2020,1.80,GHS-UCDB R2024A
Upper Middle,aggregate,,2020,2020,2.10,GHS-UCDB R2024A
```

The `region` column stores the income group name for cities (used by `build_deck.py` to look up the matching aggregate row for the "regional avg" note).

### Card Example

**Front:** What was Jakarta's CO2 emissions per capita in 2020, tonnes per person?

**Answer:** 1.97

**Notes:** Source: GHS-UCDB R2024A | All cities median: 1.80, income group median: 2.10

**Tags:** `category::emissions`, `indicator::co2_per_capita`, `entity::jakarta`, `entity_type::city`, `era::2020`

## Era Configuration

```python
"era_ranges": {
    "1990": (1990, 1990, 1990),
    "2000": (2000, 2000, 2000),
    "2010": (2010, 2010, 2010),
    "2020": (2020, 2020, 2020),
    "2025": (2025, 2025, 2025),
}
```

All exact year matches. Missing data silently skipped (e.g., PM2.5 produces no 1990 or 2025 rows).

## Testing

- **`test_ghsl.py`**: Test GeoPackage reading with a small SQLite fixture (few rows, few columns). Test BOM handling, missing values, multiple years.
- **`test_fetch_urban_data.py`**: Test median computation, CSV output format, missing data handling.
- **`test_build_deck.py`** (extend): Test deck-specific entity lookup, aggregate reference averages with new config keys.
- **Integration test**: End-to-end from GeoPackage → CSV → .apkg for urban_areas deck.

## File Summary

| File | Action |
|------|--------|
| `src/knowledge_base/config.py` | Modify — add URBAN_ENTITIES + deck |
| `src/knowledge_base/ghsl.py` | Create — GeoPackage reader |
| `src/knowledge_base/fetch_urban_data.py` | Create — orchestrator |
| `src/knowledge_base/build_deck.py` | Modify — generalize entity/reference lookup |
| `pyproject.toml` | Modify — add entry point |
| `data/urban_areas/.gitkeep` | Create |
| `tests/test_ghsl.py` | Create |
| `tests/test_fetch_urban_data.py` | Create |
| `tests/test_build_deck.py` | Modify — extend |
| `tests/test_integration.py` | Modify — extend |
