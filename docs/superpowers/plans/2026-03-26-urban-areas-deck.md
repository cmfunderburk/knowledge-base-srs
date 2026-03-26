# Urban Areas Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Knowledge Base::Urban Areas" deck using GHS-UCDB data for top 50 cities with 6 indicators across 5 eras.

**Architecture:** Local GeoPackage read via sqlite3 → per-indicator CSVs (same format as existing decks) → .apkg via existing build_deck pipeline. New `ghsl.py` reader + `fetch_urban_data.py` orchestrator. Small generalization to `build_deck.py` for deck-specific entity lookup and reference averages.

**Tech Stack:** Python 3.12+, sqlite3 (stdlib), polars, genanki, pytest

**Spec:** `docs/superpowers/specs/2026-03-26-urban-areas-deck-design.md`

---

### Task 1: GeoPackage Reader (`ghsl.py`)

**Files:**
- Create: `src/knowledge_base/ghsl.py`
- Create: `tests/test_ghsl.py`
- Create: `tests/fixtures/sample_urban.gpkg` (SQLite test fixture)

- [ ] **Step 1: Create test fixture**

Create a minimal SQLite database that mimics the GeoPackage structure with 3 cities, 2 years, and BOM-prefixed column names.

```python
# tests/conftest.py addition (or inline in test file)
# Run this once to understand the fixture structure:
# Table: GHS_UCDB_THEME_GHSL_GLOBE_R2024A
# Columns: ﻿ID_UC_G0, ﻿GH_POP_TOT_2020, ﻿GH_POP_TOT_2025
```

Create `tests/fixtures/create_urban_fixture.py`:

```python
"""One-shot script to create the test GeoPackage fixture."""
import sqlite3
from pathlib import Path

BOM = "\ufeff"
FIXTURE_PATH = Path(__file__).parent / "sample_urban.gpkg"


def create():
    con = sqlite3.connect(FIXTURE_PATH)

    # GHSL table (population, built-up per capita)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_GHSL_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}GH_POP_TOT_2020" REAL,
        "{BOM}GH_POP_TOT_2025" REAL,
        "{BOM}GH_BPC_TOT_2020" REAL,
        "{BOM}GH_BPC_TOT_2025" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_GHSL_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}GH_POP_TOT_2020", "{BOM}GH_POP_TOT_2025",
             "{BOM}GH_BPC_TOT_2020", "{BOM}GH_BPC_TOT_2025")
            VALUES (?, ?, ?, ?, ?, ?)''',
        [
            (1, 100, 10_000_000, 11_000_000, 50.0, 48.0),
            (2, 200, 5_000_000, 5_500_000, 30.0, 28.0),
            (3, 300, 2_000_000, 2_200_000, 80.0, 75.0),
        ],
    )

    # EMISSIONS table (CO2 per capita, PM2.5)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_EMISSIONS_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}EM_CO2_PEC_2020" REAL,
        "{BOM}EM_PM2_CON_2020" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_EMISSIONS_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}EM_CO2_PEC_2020", "{BOM}EM_PM2_CON_2020")
            VALUES (?, ?, ?, ?)''',
        [
            (1, 100, 5.5, 25.0),
            (2, 200, 2.0, 45.0),
            (3, 300, 8.0, 10.0),
        ],
    )

    # SOCIOECONOMIC table (life expectancy, HDI)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_SOCIOECONOMIC_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}SC_SEC_LET_2020" REAL,
        "{BOM}SC_SEC_HDI_2020" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_SOCIOECONOMIC_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}SC_SEC_LET_2020", "{BOM}SC_SEC_HDI_2020")
            VALUES (?, ?, ?, ?)''',
        [
            (1, 100, 78.5, 0.900),
            (2, 200, 72.0, 0.700),
            (3, 300, None, None),  # Missing data (like Taipei)
        ],
    )

    con.commit()
    con.close()
    print(f"Created {FIXTURE_PATH}")


if __name__ == "__main__":
    create()
```

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && python tests/fixtures/create_urban_fixture.py`

- [ ] **Step 2: Write failing tests for ghsl.fetch_indicator**

```python
# tests/test_ghsl.py
from pathlib import Path

import pytest

from knowledge_base.ghsl import fetch_indicator

FIXTURE = Path(__file__).parent / "fixtures" / "sample_urban.gpkg"


def test_fetch_population():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="GHSL",
        column_prefix="GH_POP_TOT",
        uc_ids=[100, 200, 300],
        years=[2020, 2025],
    )
    assert len(results) == 6
    # Check a specific value
    r100_2020 = [r for r in results if r["uc_id"] == 100 and r["year"] == 2020]
    assert len(r100_2020) == 1
    assert r100_2020[0]["value"] == pytest.approx(10_000_000)


def test_fetch_filters_by_uc_ids():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="GHSL",
        column_prefix="GH_POP_TOT",
        uc_ids=[100],
        years=[2020],
    )
    assert len(results) == 1
    assert results[0]["uc_id"] == 100


def test_fetch_skips_null_values():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="SOCIOECONOMIC",
        column_prefix="SC_SEC_LET",
        uc_ids=[100, 200, 300],
        years=[2020],
    )
    # City 300 has NULL life expectancy
    assert len(results) == 2
    uc_ids = {r["uc_id"] for r in results}
    assert 300 not in uc_ids


def test_fetch_nonexistent_year_returns_empty():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="EMISSIONS",
        column_prefix="EM_CO2_PEC",
        uc_ids=[100],
        years=[1990],  # Column doesn't exist in fixture
    )
    assert results == []
```

Run: `uv run pytest tests/test_ghsl.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge_base.ghsl'`

- [ ] **Step 3: Implement ghsl.py**

```python
# src/knowledge_base/ghsl.py
"""Thin reader for the GHS-UCDB GeoPackage (sqlite3-based)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

BOM = "\ufeff"

# Theme keyword → full table name
_TABLE_PREFIX = "GHS_UCDB_THEME_"
_TABLE_SUFFIX = "_GLOBE_R2024A"


def fetch_indicator(
    gpkg_path: Path,
    table_name: str,
    column_prefix: str,
    uc_ids: list[int],
    years: list[int],
) -> list[dict]:
    """Extract indicator values from the GeoPackage.

    Args:
        gpkg_path: Path to the .gpkg file.
        table_name: Theme keyword (e.g., "GHSL", "EMISSIONS").
        column_prefix: Column prefix without year (e.g., "GH_POP_TOT").
        uc_ids: List of urban centre IDs to extract.
        years: List of years to extract.

    Returns:
        List of {"uc_id": int, "year": int, "value": float} dicts.
        Rows with NULL values are excluded.
    """
    full_table = f"{_TABLE_PREFIX}{table_name}{_TABLE_SUFFIX}"
    id_col = f"{BOM}ID_UC_G0"

    con = sqlite3.connect(gpkg_path)
    try:
        # Discover which year columns actually exist
        existing_cols = {
            c[1] for c in con.execute(f'PRAGMA table_info("{full_table}")').fetchall()
        }

        year_cols = []
        for year in years:
            col = f"{BOM}{column_prefix}_{year}"
            if col in existing_cols:
                year_cols.append((year, col))

        if not year_cols:
            return []

        # Build query
        col_exprs = ", ".join(f'"{col}"' for _, col in year_cols)
        placeholders = ",".join("?" for _ in uc_ids)
        sql = f'SELECT "{id_col}", {col_exprs} FROM "{full_table}" WHERE "{id_col}" IN ({placeholders})'

        rows = con.execute(sql, uc_ids).fetchall()
    finally:
        con.close()

    results = []
    for row in rows:
        uc_id = row[0]
        for i, (year, _) in enumerate(year_cols):
            value = row[i + 1]
            if value is not None:
                results.append({"uc_id": uc_id, "year": year, "value": float(value)})

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ghsl.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/ghsl.py tests/test_ghsl.py tests/fixtures/create_urban_fixture.py tests/fixtures/sample_urban.gpkg
git commit -m "feat: add GeoPackage reader for GHS-UCDB data"
```

---

### Task 2: Urban Entities and Deck Config

**Files:**
- Modify: `src/knowledge_base/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for urban config**

Add to `tests/test_config.py`:

```python
from knowledge_base.config import DECKS, ENTITIES, URBAN_ENTITIES


def test_urban_entities_have_required_fields():
    for e in URBAN_ENTITIES:
        if e["entity_type"] == "city":
            assert "uc_id" in e, f"{e['name']} missing uc_id"
            assert "name" in e, f"entity missing name"
            assert "country" in e, f"{e['name']} missing country"
            assert "income_group" in e, f"{e['name']} missing income_group"
            assert "tag_slug" in e, f"{e['name']} missing tag_slug"
            assert "entity_type" in e
        elif e["entity_type"] == "aggregate":
            assert "name" in e
            assert "tag_slug" in e


def test_urban_entities_count():
    cities = [e for e in URBAN_ENTITIES if e["entity_type"] == "city"]
    aggregates = [e for e in URBAN_ENTITIES if e["entity_type"] == "aggregate"]
    assert len(cities) == 50
    # All Cities + income groups (High income, Upper Middle, Lower Middle, Low income)
    assert len(aggregates) >= 4


def test_urban_deck_exists():
    assert "urban_areas" in DECKS
    deck = DECKS["urban_areas"]
    assert deck["name"] == "Knowledge Base::Urban Areas"
    assert len(deck["indicators"]) == 6
    assert "entities" in deck
    assert deck["reference_entity"] == "All Cities"
    assert deck["reference_entity_type"] == "aggregate"


def test_urban_deck_eras():
    eras = DECKS["urban_areas"]["era_ranges"]
    assert set(eras.keys()) == {"1990", "2000", "2010", "2020", "2025"}
    for era, rng in eras.items():
        year = int(era)
        assert rng == (year, year, year)


def test_urban_indicators_have_ghsl_fields():
    for ind in DECKS["urban_areas"]["indicators"]:
        assert "ghsl_table" in ind, f"{ind['id']} missing ghsl_table"
        assert "ghsl_column" in ind, f"{ind['id']} missing ghsl_column"
        assert "years" in ind, f"{ind['id']} missing years"
        assert "id" in ind
        assert "name" in ind
        assert "category" in ind
        assert "unit_label" in ind
        assert "decimals" in ind
        assert "unit_prefix" in ind


def test_urban_indicators_no_wb_code():
    """Urban indicators use ghsl_column, not wb_code."""
    for ind in DECKS["urban_areas"]["indicators"]:
        assert "wb_code" not in ind


def test_all_indicators_have_required_fields():
    """Update existing test to skip wb_code check for urban deck."""
    for key, deck in DECKS.items():
        for ind in deck["indicators"]:
            assert "id" in ind, f"deck {key}: indicator missing id"
            assert "name" in ind, f"deck {key}: {ind.get('id')} missing name"
            assert "category" in ind
            assert "unit_label" in ind
            assert "decimals" in ind, f"deck {key}: {ind['id']} missing decimals"
            assert "unit_prefix" in ind, f"deck {key}: {ind['id']} missing unit_prefix"
            if key != "urban_areas":
                assert "wb_code" in ind
```

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'URBAN_ENTITIES'`

- [ ] **Step 2: Add URBAN_ENTITIES and deck config to config.py**

Add after the `REGIONS` definition in `config.py`:

```python
# ---------------------------------------------------------------------------
# Urban Entities (GHS-UCDB top 50 by 2025 population)
# ---------------------------------------------------------------------------
URBAN_ENTITIES: list[dict] = [
    # --- Aggregate references ---
    {"name": "All Cities", "entity_type": "aggregate", "tag_slug": "all_cities"},
    {"name": "High income", "entity_type": "aggregate", "tag_slug": "high_income"},
    {"name": "Upper Middle", "entity_type": "aggregate", "tag_slug": "upper_middle"},
    {"name": "Lower Middle", "entity_type": "aggregate", "tag_slug": "lower_middle"},
    {"name": "Low income", "entity_type": "aggregate", "tag_slug": "low_income"},
    # --- Cities (50) ---
    {"uc_id": 10933, "name": "Guangzhou", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "guangzhou"},
    {"uc_id": 5472, "name": "Jakarta", "entity_type": "city", "country": "Indonesia", "income_group": "Upper Middle", "tag_slug": "jakarta"},
    {"uc_id": 6090, "name": "Dhaka", "entity_type": "city", "country": "Bangladesh", "income_group": "Lower Middle", "tag_slug": "dhaka"},
    {"uc_id": 5929, "name": "Tokyo", "entity_type": "city", "country": "Japan", "income_group": "High income", "tag_slug": "tokyo"},
    {"uc_id": 7963, "name": "New Delhi", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "new_delhi"},
    {"uc_id": 11345, "name": "Shanghai", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "shanghai"},
    {"uc_id": 2323, "name": "Manila", "entity_type": "city", "country": "Philippines", "income_group": "Lower Middle", "tag_slug": "manila"},
    {"uc_id": 4605, "name": "Cairo", "entity_type": "city", "country": "Egypt", "income_group": "Lower Middle", "tag_slug": "cairo"},
    {"uc_id": 11352, "name": "Kolkata", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "kolkata"},
    {"uc_id": 348, "name": "Seoul", "entity_type": "city", "country": "South Korea", "income_group": "High income", "tag_slug": "seoul"},
    {"uc_id": 2457, "name": "Karachi", "entity_type": "city", "country": "Pakistan", "income_group": "Lower Middle", "tag_slug": "karachi"},
    {"uc_id": 7599, "name": "Mumbai", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "mumbai"},
    {"uc_id": 7277, "name": "São Paulo", "entity_type": "city", "country": "Brazil", "income_group": "Upper Middle", "tag_slug": "sao_paulo"},
    {"uc_id": 2315, "name": "Bangkok", "entity_type": "city", "country": "Thailand", "income_group": "Upper Middle", "tag_slug": "bangkok"},
    {"uc_id": 8745, "name": "Beijing", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "beijing"},
    {"uc_id": 5402, "name": "Mexico City", "entity_type": "city", "country": "México", "income_group": "Upper Middle", "tag_slug": "mexico_city"},
    {"uc_id": 9558, "name": "Bengaluru", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "bengaluru"},
    {"uc_id": 5239, "name": "Ho Chi Minh City", "entity_type": "city", "country": "Vietnam", "income_group": "Lower Middle", "tag_slug": "ho_chi_minh_city"},
    {"uc_id": 2576, "name": "Moscow", "entity_type": "city", "country": "Russia", "income_group": "Upper Middle", "tag_slug": "moscow"},
    {"uc_id": 7794, "name": "Lahore", "entity_type": "city", "country": "Pakistan", "income_group": "Lower Middle", "tag_slug": "lahore"},
    {"uc_id": 2637, "name": "Istanbul", "entity_type": "city", "country": "Turkey", "income_group": "Upper Middle", "tag_slug": "istanbul"},
    {"uc_id": 8099, "name": "New York City", "entity_type": "city", "country": "United States", "income_group": "High income", "tag_slug": "new_york_city"},
    {"uc_id": 4443, "name": "Buenos Aires", "entity_type": "city", "country": "Argentina", "income_group": "Upper Middle", "tag_slug": "buenos_aires"},
    {"uc_id": 2007, "name": "Los Angeles", "entity_type": "city", "country": "United States", "income_group": "High income", "tag_slug": "los_angeles"},
    {"uc_id": 1876, "name": "Kinshasa", "entity_type": "city", "country": "Democratic Republic of the Congo", "income_group": "Low income", "tag_slug": "kinshasa"},
    {"uc_id": 1289, "name": "Lagos", "entity_type": "city", "country": "Nigeria", "income_group": "Lower Middle", "tag_slug": "lagos"},
    {"uc_id": 4399, "name": "Osaka", "entity_type": "city", "country": "Japan", "income_group": "High income", "tag_slug": "osaka"},
    {"uc_id": 1082, "name": "Luanda", "entity_type": "city", "country": "Angola", "income_group": "Lower Middle", "tag_slug": "luanda"},
    {"uc_id": 11199, "name": "Suzhou", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "suzhou"},
    {"uc_id": 10300, "name": "Chennai", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "chennai"},
    {"uc_id": 2171, "name": "Lima", "entity_type": "city", "country": "Peru", "income_group": "Upper Middle", "tag_slug": "lima"},
    {"uc_id": 11407, "name": "Shantou", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "shantou"},
    {"uc_id": 3881, "name": "Bogota", "entity_type": "city", "country": "Colombia", "income_group": "Upper Middle", "tag_slug": "bogota"},
    {"uc_id": 5816, "name": "London", "entity_type": "city", "country": "United Kingdom", "income_group": "High income", "tag_slug": "london"},
    {"uc_id": 7799, "name": "Rio de Janeiro", "entity_type": "city", "country": "Brazil", "income_group": "Upper Middle", "tag_slug": "rio_de_janeiro"},
    {"uc_id": 10576, "name": "Hajipur", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "hajipur"},
    {"uc_id": 1142, "name": "Taipei", "entity_type": "city", "country": "Taiwan", "income_group": "High income", "tag_slug": "taipei"},
    {"uc_id": 9524, "name": "Hyderabad", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "hyderabad"},
    {"uc_id": 5174, "name": "Tehran", "entity_type": "city", "country": "Iran", "income_group": "Lower Middle", "tag_slug": "tehran"},
    {"uc_id": 2878, "name": "Paris", "entity_type": "city", "country": "France", "income_group": "High income", "tag_slug": "paris"},
    {"uc_id": 3570, "name": "Dar es-Salaam", "entity_type": "city", "country": "Tanzania", "income_group": "Lower Middle", "tag_slug": "dar_es_salaam"},
    {"uc_id": 5748, "name": "Bandung", "entity_type": "city", "country": "Indonesia", "income_group": "Upper Middle", "tag_slug": "bandung"},
    {"uc_id": 3512, "name": "Johannesburg", "entity_type": "city", "country": "South Africa", "income_group": "Upper Middle", "tag_slug": "johannesburg"},
    {"uc_id": 8557, "name": "Chongqing", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "chongqing"},
    {"uc_id": 1648, "name": "Kuala Lumpur", "entity_type": "city", "country": "Malaysia", "income_group": "Upper Middle", "tag_slug": "kuala_lumpur"},
    {"uc_id": 10131, "name": "Wuhan", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "wuhan"},
    {"uc_id": 10887, "name": "Nanjing", "entity_type": "city", "country": "China", "income_group": "Upper Middle", "tag_slug": "nanjing"},
    {"uc_id": 3026, "name": "Riyadh", "entity_type": "city", "country": "Saudi Arabia", "income_group": "High income", "tag_slug": "riyadh"},
    {"uc_id": 6143, "name": "Ahmedabad", "entity_type": "city", "country": "India", "income_group": "Lower Middle", "tag_slug": "ahmedabad"},
    {"uc_id": 5213, "name": "Nagoya", "entity_type": "city", "country": "Japan", "income_group": "High income", "tag_slug": "nagoya"},
]
```

Add the deck entry to the `DECKS` dict:

```python
    "urban_areas": {
        "name": "Knowledge Base::Urban Areas",
        "deck_id": 2026032604,
        "output": "knowledge_base_urban_areas.apkg",
        "data_dir": "data/urban_areas",
        "gpkg_path": "resources/OECD/GHS_UCDB_GLOBE_R2024A_V1_1/GHS_UCDB_GLOBE_R2024A.gpkg",
        "entities": URBAN_ENTITIES,
        "reference_entity": "All Cities",
        "reference_entity_type": "aggregate",
        "era_ranges": {
            "1990": (1990, 1990, 1990),
            "2000": (2000, 2000, 2000),
            "2010": (2010, 2010, 2010),
            "2020": (2020, 2020, 2020),
            "2025": (2025, 2025, 2025),
        },
        "indicators": [
            {
                "id": "population",
                "name": "Population",
                "category": "demographics",
                "unit_label": "millions",
                "ghsl_table": "GHSL",
                "ghsl_column": "GH_POP_TOT",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1_000_000,
                "years": [1990, 2000, 2010, 2020, 2025],
            },
            {
                "id": "co2_per_capita",
                "name": "CO2 emissions per capita",
                "category": "emissions",
                "unit_label": "tonnes per person",
                "ghsl_table": "EMISSIONS",
                "ghsl_column": "EM_CO2_PEC",
                "decimals": 2,
                "unit_prefix": "",
                "scale_factor": 1,
                "years": [1990, 2000, 2010, 2020],
            },
            {
                "id": "pm25_concentration",
                "name": "PM2.5 concentration",
                "category": "emissions",
                "unit_label": "\u00b5g/m\u00b3",
                "ghsl_table": "EMISSIONS",
                "ghsl_column": "EM_PM2_CON",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1,
                "years": [2000, 2010, 2020],
            },
            {
                "id": "life_expectancy",
                "name": "Life expectancy",
                "category": "socioeconomic",
                "unit_label": "years",
                "ghsl_table": "SOCIOECONOMIC",
                "ghsl_column": "SC_SEC_LET",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1,
                "years": [1990, 2000, 2010, 2020],
            },
            {
                "id": "built_up_per_capita",
                "name": "Built-up area per capita",
                "category": "urban_form",
                "unit_label": "m\u00b2 per person",
                "ghsl_table": "GHSL",
                "ghsl_column": "GH_BPC_TOT",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1,
                "years": [1990, 2000, 2010, 2020, 2025],
            },
            {
                "id": "hdi",
                "name": "Human Development Index",
                "category": "socioeconomic",
                "unit_label": "index (0\u20131)",
                "ghsl_table": "SOCIOECONOMIC",
                "ghsl_column": "SC_SEC_HDI",
                "decimals": 3,
                "unit_prefix": "",
                "scale_factor": 1,
                "years": [1990, 2000, 2010, 2020],
            },
        ],
    },
```

- [ ] **Step 3: Update the existing `test_all_indicators_have_required_fields` test**

Replace the existing `test_all_indicators_have_required_fields` in `tests/test_config.py` with the version from Step 1 that skips `wb_code` check for urban_areas deck.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add urban entities and deck config for GHS-UCDB"
```

---

### Task 3: Fetch Urban Data (`fetch_urban_data.py`)

**Files:**
- Create: `src/knowledge_base/fetch_urban_data.py`
- Create: `tests/test_fetch_urban_data.py`
- Create: `data/urban_areas/.gitkeep`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fetch_urban_data.py
import polars as pl
import pytest
from pathlib import Path

from knowledge_base.fetch_urban_data import (
    compute_median_aggregates,
    build_urban_indicator_dataframe,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_median_aggregates():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
        {"entity": "CityB", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 20.0, "source": "test"},
        {"entity": "CityC", "entity_type": "city", "region": "Lower Middle", "era": "2020", "year": 2020, "value": 5.0, "source": "test"},
    ]
    aggregates = compute_median_aggregates(rows, "test")
    # All Cities median of [5, 10, 20] = 10.0
    all_cities = [a for a in aggregates if a["entity"] == "All Cities"]
    assert len(all_cities) == 1
    assert all_cities[0]["value"] == pytest.approx(10.0)
    assert all_cities[0]["entity_type"] == "aggregate"
    assert all_cities[0]["era"] == "2020"
    # High income median of [10, 20] = 15.0
    high = [a for a in aggregates if a["entity"] == "High income"]
    assert len(high) == 1
    assert high[0]["value"] == pytest.approx(15.0)
    # Lower Middle median of [5] = 5.0
    lower = [a for a in aggregates if a["entity"] == "Lower Middle"]
    assert len(lower) == 1
    assert lower[0]["value"] == pytest.approx(5.0)


def test_compute_median_aggregates_multiple_eras():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2010", "year": 2010, "value": 8.0, "source": "test"},
    ]
    aggregates = compute_median_aggregates(rows, "test")
    eras = {a["era"] for a in aggregates if a["entity"] == "All Cities"}
    assert eras == {"2020", "2010"}


def test_build_urban_indicator_dataframe():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
    ]
    df = build_urban_indicator_dataframe(rows)
    assert len(df) == 1
    assert df.columns == ["entity", "entity_type", "region", "era", "year", "value", "source"]
```

Run: `uv run pytest tests/test_fetch_urban_data.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 2: Implement fetch_urban_data.py**

```python
# src/knowledge_base/fetch_urban_data.py
"""Fetch GHS-UCDB indicator data and write per-indicator CSV files."""

from __future__ import annotations

import statistics
from pathlib import Path

import polars as pl

from knowledge_base.config import DECKS, URBAN_ENTITIES
from knowledge_base.ghsl import fetch_indicator

EXPECTED_COLUMNS = ["entity", "entity_type", "region", "era", "year", "value", "source"]
GHSL_SOURCE = "GHS-UCDB R2024A"


def _column_schema() -> dict[str, type]:
    return {
        "entity": pl.Utf8,
        "entity_type": pl.Utf8,
        "region": pl.Utf8,
        "era": pl.Utf8,
        "year": pl.Int64,
        "value": pl.Float64,
        "source": pl.Utf8,
    }


def build_urban_indicator_dataframe(rows: list[dict]) -> pl.DataFrame:
    normalised = [{col: row.get(col) for col in EXPECTED_COLUMNS} for row in rows]
    return pl.DataFrame(normalised, schema=_column_schema())


def compute_median_aggregates(city_rows: list[dict], source: str) -> list[dict]:
    """Compute All Cities and per-income-group median aggregates.

    Groups city_rows by era, computes median for All Cities and
    for each distinct income group (stored in the 'region' field).
    """
    by_era: dict[str, list[dict]] = {}
    for row in city_rows:
        by_era.setdefault(row["era"], []).append(row)

    aggregates = []
    for era, rows in by_era.items():
        values = [r["value"] for r in rows]
        year = rows[0]["year"]

        # All Cities median
        aggregates.append({
            "entity": "All Cities",
            "entity_type": "aggregate",
            "region": "",
            "era": era,
            "year": year,
            "value": statistics.median(values),
            "source": source,
        })

        # Per income group
        by_group: dict[str, list[float]] = {}
        for row in rows:
            by_group.setdefault(row["region"], []).append(row["value"])

        for group, group_values in by_group.items():
            aggregates.append({
                "entity": group,
                "entity_type": "aggregate",
                "region": "",
                "era": era,
                "year": year,
                "value": statistics.median(group_values),
                "source": source,
            })

    return aggregates


def _run(output_dir: Path | None = None) -> None:
    deck = DECKS["urban_areas"]
    indicators = deck["indicators"]
    gpkg_path = Path(deck["gpkg_path"])

    if output_dir is None:
        output_dir = Path(deck["data_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build entity lookup: uc_id → entity dict
    cities = [e for e in URBAN_ENTITIES if e["entity_type"] == "city"]
    entity_by_id = {e["uc_id"]: e for e in cities}
    uc_ids = list(entity_by_id.keys())

    for indicator in indicators:
        indicator_id = indicator["id"]
        print(f"Processing {indicator_id}…")

        records = fetch_indicator(
            gpkg_path=gpkg_path,
            table_name=indicator["ghsl_table"],
            column_prefix=indicator["ghsl_column"],
            uc_ids=uc_ids,
            years=indicator["years"],
        )

        city_rows: list[dict] = []
        for record in records:
            entity = entity_by_id.get(record["uc_id"])
            if entity is None:
                continue
            city_rows.append({
                "entity": entity["name"],
                "entity_type": "city",
                "region": entity["income_group"],
                "era": str(record["year"]),
                "year": record["year"],
                "value": float(record["value"]),
                "source": GHSL_SOURCE,
            })

        # Compute aggregates
        aggregates = compute_median_aggregates(city_rows, GHSL_SOURCE)

        all_rows = city_rows + aggregates
        df = build_urban_indicator_dataframe(all_rows)
        out_path = output_dir / f"{indicator_id}.csv"
        df.write_csv(out_path)
        print(f"  wrote {len(df)} rows → {out_path}")

    print("Done.")


def main() -> None:
    """CLI entry point."""
    _run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create data directory**

```bash
mkdir -p data/urban_areas && touch data/urban_areas/.gitkeep
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetch_urban_data.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/fetch_urban_data.py tests/test_fetch_urban_data.py data/urban_areas/.gitkeep
git commit -m "feat: add fetch_urban_data orchestrator for GHS-UCDB → CSV pipeline"
```

---

### Task 4: Generalize `build_deck.py`

**Files:**
- Modify: `src/knowledge_base/build_deck.py`
- Modify: `tests/test_build_deck.py`

- [ ] **Step 1: Write failing tests for deck-specific entity lookup and reference averages**

Add to `tests/test_build_deck.py`:

```python
def test_compute_reference_averages_with_custom_entity():
    """Test reference averages using aggregate entity names."""
    df = pl.DataFrame({
        "entity": ["All Cities", "High income", "CityA", "CityB"],
        "entity_type": ["aggregate", "aggregate", "city", "city"],
        "region": ["", "", "High income", "High income"],
        "era": ["2020", "2020", "2020", "2020"],
        "year": [2020, 2020, 2020, 2020],
        "value": [15.0, 20.0, 10.0, 20.0],
        "source": ["test", "test", "test", "test"],
    })
    world_avg, region_avgs = compute_reference_averages(
        df, "2020",
        reference_entity="All Cities",
        reference_entity_type="aggregate",
    )
    assert world_avg == pytest.approx(15.0)
    assert region_avgs["High income"] == pytest.approx(20.0)


def test_compute_reference_averages_backward_compatible():
    """Existing behavior unchanged when no custom args passed."""
    df = pl.read_csv(FIXTURES / "sample_gdp.csv")
    world_avg, region_avgs = compute_reference_averages(df, "current")
    assert world_avg == pytest.approx(17500)
    assert region_avgs["South Asia"] == pytest.approx(7200)
```

Run: `uv run pytest tests/test_build_deck.py::test_compute_reference_averages_with_custom_entity -v`
Expected: FAIL — `TypeError: compute_reference_averages() got an unexpected keyword argument 'reference_entity'`

- [ ] **Step 2: Generalize compute_reference_averages**

Update the function signature and body in `build_deck.py`:

```python
def compute_reference_averages(
    df: pl.DataFrame,
    era: str,
    reference_entity: str = "World",
    reference_entity_type: str = "region",
) -> tuple[float | None, dict[str, float]]:
    """Extract reference entity value as world_avg and group rows as a dict.

    For World Bank decks: reference_entity="World", reference_entity_type="region".
    For urban decks: reference_entity="All Cities", reference_entity_type="aggregate".
    """
    era_df = df.filter(pl.col("era") == era)

    # World/All Cities average
    world_rows = era_df.filter(pl.col("entity") == reference_entity)
    world_avg: float | None = None
    if len(world_rows) > 0:
        world_avg = world_rows["value"][0]

    # Regional/income group averages
    region_rows = era_df.filter(
        (pl.col("entity_type") == reference_entity_type)
        & (pl.col("entity") != reference_entity)
    )
    region_avgs: dict[str, float] = {}
    for row in region_rows.iter_rows(named=True):
        region_avgs[row["entity"]] = row["value"]

    return world_avg, region_avgs
```

- [ ] **Step 3: Update _run to use deck-specific entities and reference config**

In `build_deck.py`, update `_find_entity_config` to accept an entity list and update `_run` to pass the deck's entity list and reference config:

Replace `_find_entity_config`:

```python
def _find_entity_config(entity_name: str, entities: list[dict] | None = None) -> dict | None:
    """Look up entity config by name from the given entity list."""
    for e in (entities or ENTITIES):
        if e["name"] == entity_name:
            return e
    return None
```

In `_run`, after `deck_cfg = DECKS[deck_key]`, add:

```python
    entities = deck_cfg.get("entities", ENTITIES)
    ref_entity = deck_cfg.get("reference_entity", "World")
    ref_entity_type = deck_cfg.get("reference_entity_type", "region")
```

Update the reference averages computation loop:

```python
        for era in eras:
            ref_by_era[era] = compute_reference_averages(
                df, era,
                reference_entity=ref_entity,
                reference_entity_type=ref_entity_type,
            )
```

Update the entity lookup call:

```python
            entity_cfg = _find_entity_config(entity_name, entities)
```

Update the card_rows filter to exclude aggregates too:

```python
        card_rows = df.filter(
            ~pl.col("entity_type").is_in(["region", "aggregate"])
        )
```

- [ ] **Step 4: Run all tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/build_deck.py tests/test_build_deck.py
git commit -m "feat: generalize build_deck for deck-specific entities and references"
```

---

### Task 5: Entry Point and Integration Test

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add entry point to pyproject.toml**

Add to `[project.scripts]`:

```toml
fetch-urban-data = "knowledge_base.fetch_urban_data:main"
```

- [ ] **Step 2: Write integration test for urban areas deck**

Add to `tests/test_integration.py`:

```python
def test_build_urban_deck_from_fixtures(tmp_path):
    """End-to-end: fixture CSV → .apkg for urban areas deck."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create a minimal population CSV matching urban_areas deck format
    csv_content = (
        "entity,entity_type,region,era,year,value,source\n"
        "All Cities,aggregate,,2020,2020,15000000,GHS-UCDB R2024A\n"
        "High income,aggregate,,2020,2020,20000000,GHS-UCDB R2024A\n"
        "Tokyo,city,High income,2020,2020,33000000,GHS-UCDB R2024A\n"
        "Jakarta,city,Upper Middle,2020,2020,38000000,GHS-UCDB R2024A\n"
    )
    (data_dir / "population.csv").write_text(csv_content)

    output_path = tmp_path / "test_urban.apkg"

    _run("urban_areas", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
```

- [ ] **Step 3: Run integration test**

Run: `uv run pytest tests/test_integration.py -v`
Expected: Both integration tests PASS

- [ ] **Step 4: Sync deps and run full test suite**

```bash
uv sync
uv run pytest -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_integration.py
git commit -m "feat: add fetch-urban-data entry point and integration test"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update documentation**

Update the Quick Reference section to include:

```
uv run fetch-urban-data           # extract GHS-UCDB → data/urban_areas/*.csv
```

Update Available deck keys line:

```
Available deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`, `urban_areas`
```

Update the test count to reflect new tests.

Add a note under Architecture:

```
- `ghsl.py` — GHS-UCDB GeoPackage reader (sqlite3, no auth)
- `fetch_urban_data.py` — extracts GHS-UCDB data, computes median aggregates, writes CSVs
```

Add a note under Data:

```
- `resources/OECD/GHS_UCDB_GLOBE_R2024A_V1_1/` — GHS Urban Centre Database (committed GeoPackage, ~283MB)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with urban areas deck"
```
