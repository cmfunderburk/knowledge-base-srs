# Anki with Uncertainty OWID Deck — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-stage data pipeline that fetches development/health/energy/geography indicators from the World Bank API and UN data, produces curated CSVs, and generates an Anki `.apkg` deck using the Anki with Uncertainty "Interval" note type.

**Architecture:** `fetch_data.py` downloads from the World Bank API (and a bundled UN WUP CSV for city populations), writes one CSV per indicator to `data/`. `build_deck.py` reads those CSVs, generates question text with reference-class context, and produces `knowledge_base.apkg` via genanki. A shared `config.py` module holds entity lists, indicator metadata, and World Bank API codes.

**Tech Stack:** Python 3.12+, uv (package manager), genanki, httpx (World Bank API), polars (CSV processing)

**Spec:** `docs/superpowers/specs/2026-03-23-anki-uncertainty-owid-deck-design.md`

---

## File Structure

```
knowledge-base/
├── pyproject.toml              # uv project: genanki, httpx, polars, pytest
├── src/
│   └── knowledge_base/
│       ├── __init__.py
│       ├── config.py           # Entity lists, indicator metadata, WB API codes, tag slugs
│       ├── wb_api.py           # World Bank API client (fetch indicator data for entities/years)
│       ├── fetch_data.py       # Stage 1: download & clean → data/*.csv
│       └── build_deck.py       # Stage 2: data/*.csv → knowledge_base.apkg
├── data/                       # Curated CSVs (one per indicator), gitignored
├── resources/
│   ├── Anki_with_uncertainty__example_deck.apkg
│   └── un_wup_cities.csv       # UN World Urbanization Prospects top-100 cities (bundled)
├── tests/
│   ├── __init__.py
│   ├── test_config.py          # Entity/indicator consistency checks
│   ├── test_wb_api.py          # API client unit tests (mocked HTTP)
│   ├── test_fetch_data.py      # CSV output format validation
│   ├── test_build_deck.py      # Card generation logic tests
│   └── fixtures/
│       ├── sample_gdp.csv          # Small fixture CSV for build_deck tests
│       └── sample_city_population.csv  # City population fixture
└── docs/
    └── superpowers/
        ├── specs/...
        └── plans/...
```

### Key API Code Reference

These World Bank indicator codes were verified against the live API on 2026-03-23:

| Indicator | WB Code | Unit (current) |
|-----------|---------|----------------|
| GDP per capita (PPP) | `NY.GDP.PCAP.PP.KD` | constant 2021 international $ |
| Poverty headcount | `SI.POV.DDAY` | % below $3.00/day (2021 PPP) |
| Gini index | `SI.POV.GINI` | 0–100 (country-level only, no regional aggregates) |
| Trade (% of GDP) | `NE.TRD.GNFS.ZS` | % |
| Life expectancy | `SP.DYN.LE00.IN` | years |
| Under-5 mortality | `SH.DYN.MORT` | per 1,000 live births |
| Maternal mortality | `SH.STA.MMRT` | per 100,000 live births |
| Fertility rate | `SP.DYN.TFRT.IN` | births per woman |
| CO2 per capita | `EN.GHG.CO2.PC.CE.AR5` | t CO2e/capita |
| Renewable electricity | `EG.ELC.RNEW.ZS` | % of total |
| Energy intensity | `EG.EGY.PRIM.PP.KD` | MJ per $2021 PPP GDP |
| Population | `SP.POP.TOTL` | people |
| Land area | `AG.LND.TOTL.K2` | sq. km |

Regional aggregate codes: `WLD` (World), `SSF` (Sub-Saharan Africa), `SAS` (South Asia), `EAS` (East Asia & Pacific), `LCN` (Latin America & Caribbean), `MEA` (Middle East & North Africa), `ECS` (Europe & Central Asia)

### Spec Deviations (from API research)

The design spec references 2017 PPP and $2.15/day poverty line. The World Bank has since rebased:
- GDP per capita and energy intensity now use **2021 international $** (not 2017)
- Poverty line is now **$3.00/day (2021 PPP)** (not $2.15/day 2017 PPP)
- CO2 uses EDGAR-based `EN.GHG.CO2.PC.CE.AR5` (old indicator deleted)
- Gini has no regional aggregates — Notes field for Gini cards will show world avg only (computed from available country data), no regional avg

These are data source realities; the question format and card templates remain as designed.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/knowledge_base/__init__.py`
- Create: `.gitignore`
- Create: `data/.gitkeep`

- [ ] **Step 1: Initialize uv project**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
uv init --lib --name knowledge-base
```

- [ ] **Step 2: Edit pyproject.toml**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "knowledge-base"
version = "0.1.0"
description = "Anki with Uncertainty deck generator for OWID-style knowledge"
requires-python = ">=3.12"
dependencies = [
    "genanki>=0.13",
    "httpx>=0.27",
    "polars>=1.0",
]

[project.scripts]
fetch-data = "knowledge_base.fetch_data:main"
build-deck = "knowledge_base.build_deck:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Set up directory structure**

```bash
mkdir -p src/knowledge_base tests/fixtures data
touch src/knowledge_base/__init__.py tests/__init__.py data/.gitkeep
```

- [ ] **Step 4: Create .gitignore**

```gitignore
data/*.csv
*.apkg
__pycache__/
.venv/
```

- [ ] **Step 5: Install dependencies**

```bash
uv sync
```

- [ ] **Step 6: Verify pytest runs**

```bash
uv run pytest
```

Expected: `no tests ran` (0 collected), exit code 0 (or 5 for no tests).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/ tests/ data/.gitkeep .gitignore .python-version
git commit -m "feat: scaffold project with uv, genanki, httpx, polars"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/knowledge_base/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config consistency tests**

```python
# tests/test_config.py
from knowledge_base.config import ENTITIES, INDICATORS, REGIONS, ERA_RANGES


def test_all_entities_have_required_fields():
    for e in ENTITIES:
        assert "name" in e
        assert "entity_type" in e, f"{e['name']} missing entity_type"
        assert e["entity_type"] in ("region", "major", "long_tail")
        if e["entity_type"] != "region":
            assert "region" in e, f"{e['name']} missing region"
            assert "iso3" in e, f"{e['name']} missing iso3"
        else:
            assert "wb_code" in e, f"{e['name']} missing wb_code"


def test_all_indicators_have_required_fields():
    for ind in INDICATORS:
        assert "id" in ind
        assert "name" in ind
        assert "category" in ind
        assert "unit_label" in ind
        assert "wb_code" in ind or ind["id"] == "city_population"


def test_region_names_consistent():
    """Every non-region entity's region field must match a region entity name."""
    region_names = {e["name"] for e in ENTITIES if e["entity_type"] == "region"}
    for e in ENTITIES:
        if e["entity_type"] != "region" and "region" in e:
            assert e["region"] in region_names, (
                f"{e['name']}'s region '{e['region']}' not in regions"
            )


def test_entity_count():
    """Sanity check: ~47 entities as designed."""
    assert 45 <= len(ENTITIES) <= 55


def test_era_ranges():
    assert "1960" in ERA_RANGES
    assert "1990" in ERA_RANGES
    assert "current" in ERA_RANGES
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError — `config` module doesn't exist yet.

- [ ] **Step 3: Write config.py**

Create `src/knowledge_base/config.py` with the full entity list (47 entities with name, entity_type, region, iso3/wb_code), all 14 indicators (with id, name, category, unit_label, wb_code, question_template, time_invariant flag), era ranges, and region mappings.

Key data structures:

```python
ENTITIES: list[dict]  # 47 entries with name, entity_type, region, iso3/wb_code
INDICATORS: list[dict]  # 14 entries with id, name, category, unit_label, wb_code, etc.
REGIONS: list[dict]  # subset of ENTITIES where entity_type == "region"
ERA_RANGES: dict[str, tuple[int, int, int]]  # (range_start, range_end, target_year)
# {"1960": (1955, 1965, 1960), "1990": (1988, 1992, 1990), "current": (2020, 2026, 2026)}
# For "current", target_year=2026 means "pick the most recent year within range"
```

Each indicator dict includes:
- `id`: slug for filenames and tags (e.g., `"gdp_pc_ppp"`)
- `name`: display name (e.g., `"GDP per capita (PPP)"`)
- `category`: one of `"development"`, `"health"`, `"energy"`, `"geography"`
- `unit_label`: string for question text (e.g., `"in 2021 international dollars"`)
- `wb_code`: World Bank API indicator code (or `None` for city_population)
- `question_template`: format string like `"What was {entity}'s {name} in {year}, {unit_label}?"`
- `time_invariant`: bool (True only for land_area)
- `current_only`: bool (True only for city_population)
- `has_regional_aggregates`: bool (False for Gini)

Each entity dict includes:
- `name`: display name (e.g., `"India"`)
- `entity_type`: `"region"`, `"major"`, or `"long_tail"`
- `region`: parent region name (absent for regions themselves)
- `iso3`: ISO 3166-1 alpha-3 code for countries (e.g., `"IND"`)
- `wb_code`: World Bank aggregate code for regions (e.g., `"SAS"`)
- `tag_slug`: lowercase slug for Anki tags (e.g., `"india"`, `"sub_saharan_africa"`)

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add entity/indicator/era configuration"
```

---

## Task 3: World Bank API Client

**Files:**
- Create: `src/knowledge_base/wb_api.py`
- Create: `tests/test_wb_api.py`

- [ ] **Step 1: Write API client tests**

```python
# tests/test_wb_api.py
import json
import httpx
import pytest
from unittest.mock import patch, Mock
from knowledge_base.wb_api import fetch_indicator


# Sample World Bank API response shape
SAMPLE_WB_RESPONSE = [
    {"page": 1, "pages": 1, "per_page": 50, "total": 2},
    [
        {
            "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
            "country": {"id": "IN", "value": "India"},
            "countryiso3code": "IND",
            "date": "1990",
            "value": 873277798,
        },
        {
            "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
            "country": {"id": "IN", "value": "India"},
            "countryiso3code": "IND",
            "date": "1960",
            "value": 450547679,
        },
    ],
]


def _mock_response(data, status_code=200):
    """Create a properly constructed httpx.Response with JSON body."""
    return httpx.Response(
        status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
    )


def test_fetch_indicator_parses_response():
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(SAMPLE_WB_RESPONSE)):
        results = fetch_indicator("SP.POP.TOTL", ["IND"], 1955, 1995)

    assert len(results) == 2
    assert results[0]["country_code"] == "IND"
    assert results[0]["year"] == 1990
    assert results[0]["value"] == 873277798


def test_fetch_indicator_skips_null_values():
    response_with_null = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 2},
        [
            {
                "indicator": {"id": "SI.POV.GINI"},
                "country": {"id": "IN", "value": "India"},
                "countryiso3code": "IND",
                "date": "2020",
                "value": None,
            },
            {
                "indicator": {"id": "SI.POV.GINI"},
                "country": {"id": "IN", "value": "India"},
                "countryiso3code": "IND",
                "date": "2019",
                "value": 35.7,
            },
        ],
    ]
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(response_with_null)):
        results = fetch_indicator("SI.POV.GINI", ["IND"], 2015, 2025)

    assert len(results) == 1
    assert results[0]["value"] == 35.7


def test_fetch_indicator_handles_empty_response():
    empty_response = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 0},
        None,
    ]
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(empty_response)):
        results = fetch_indicator("SP.POP.TOTL", ["IND"], 1950, 1950)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_wb_api.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write wb_api.py**

```python
# src/knowledge_base/wb_api.py
"""Thin client for the World Bank Indicators API v2."""

import httpx

WB_API_BASE = "https://api.worldbank.org/v2"


def fetch_indicator(
    indicator_code: str,
    country_codes: list[str],
    year_start: int,
    year_end: int,
) -> list[dict]:
    """Fetch indicator data for given countries and year range.

    Returns list of dicts with keys: country_code, year, value.
    Null values are excluded.
    """
    countries = ";".join(country_codes)
    url = f"{WB_API_BASE}/country/{countries}/indicator/{indicator_code}"
    params = {
        "date": f"{year_start}:{year_end}",
        "format": "json",
        "per_page": 10000,
    }

    resp = httpx.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if len(data) < 2 or data[1] is None:
        return []

    # Guard against silent pagination truncation
    if data[0]["pages"] > 1:
        raise RuntimeError(
            f"Response has {data[0]['pages']} pages — increase per_page or paginate"
        )

    results = []
    for record in data[1]:
        if record["value"] is not None:
            results.append({
                "country_code": record["countryiso3code"],
                "year": int(record["date"]),
                "value": record["value"],
            })

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_wb_api.py -v
```

Expected: all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/wb_api.py tests/test_wb_api.py
git commit -m "feat: add World Bank API client"
```

---

## Task 4: Data Fetcher (`fetch_data.py`)

**Files:**
- Create: `src/knowledge_base/fetch_data.py`
- Create: `tests/test_fetch_data.py`

- [ ] **Step 1: Write tests for era selection and CSV output**

```python
# tests/test_fetch_data.py
import polars as pl
import pytest
from knowledge_base.fetch_data import (
    select_best_year_for_era,
    build_indicator_dataframe,
    EXPECTED_COLUMNS,
)


def test_select_best_year_for_era_prefers_target():
    """Should pick year closest to era target."""
    records = [
        {"country_code": "IND", "year": 1958, "value": 100},
        {"country_code": "IND", "year": 1960, "value": 110},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960")
    assert best["year"] == 1960


def test_select_best_year_for_era_picks_closest():
    """When target year is missing, pick closest within range."""
    records = [
        {"country_code": "IND", "year": 1956, "value": 100},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960")
    assert best["year"] == 1963  # |1963-1960|=3 < |1956-1960|=4


def test_select_best_year_for_era_returns_none_outside_range():
    """Years outside the acceptable range should be rejected."""
    records = [
        {"country_code": "IND", "year": 1950, "value": 100},
    ]
    best = select_best_year_for_era(records, "IND", "1960")
    assert best is None


def test_select_best_year_for_current_era():
    """Current era picks the most recent year."""
    records = [
        {"country_code": "IND", "year": 2020, "value": 100},
        {"country_code": "IND", "year": 2022, "value": 110},
        {"country_code": "IND", "year": 2023, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "current")
    assert best["year"] == 2023


def test_build_indicator_dataframe_columns():
    """Output DataFrame must have the expected column schema."""
    rows = [{
        "entity": "India",
        "entity_type": "major",
        "region": "South Asia",
        "era": "1990",
        "year": 1990,
        "value": 1806.0,
        "source": "World Bank WDI",
    }]
    df = build_indicator_dataframe(rows)
    assert set(df.columns) == set(EXPECTED_COLUMNS)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_fetch_data.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write fetch_data.py**

Implement the full data fetcher:

1. For each World Bank indicator in `INDICATORS`:
   - Build the list of country/region codes from `ENTITIES`
   - Call `fetch_indicator()` with the full year range (1955–2026)
   - For each entity × era, call `select_best_year_for_era()` to pick the best data point
   - Collect rows into a list of dicts
   - Write to `data/{indicator_id}.csv` via polars

2. `select_best_year_for_era(records, country_code, era)`:
   - Filter records to the given country_code
   - Look up the era's acceptable range from `ERA_RANGES`
   - For `"current"`: pick the most recent year at or above 2020
   - For `"1960"`/`"1990"`: pick the year closest to the target within the range
   - Return the best record, or `None` if nothing in range

3. `main(output_dir: Path = Path("data"))` — accepts an optional output directory (default `Path("data")`) so it works both as a CLI entry point and in tests. Orchestrates the above and prints progress.

City population data (`city_population` indicator) is handled separately: read from `resources/un_wup_cities.csv` (bundled), filter to top ~100 cities, write to `data/city_population.csv` in the same column format.

Define the constant `EXPECTED_COLUMNS = ["entity", "entity_type", "region", "era", "year", "value", "source"]` for use in tests and validation.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_fetch_data.py -v
```

Expected: all 5 pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/fetch_data.py tests/test_fetch_data.py
git commit -m "feat: add data fetcher with era selection logic"
```

---

## Task 5: UN City Population Data

**Files:**
- Create: `resources/un_wup_cities.csv`

The UN World Urbanization Prospects data is not available via a clean API. This task prepares a bundled CSV of the ~top 100 cities by metro population.

- [ ] **Step 1: Source the data**

Download the UN WUP 2024 dataset (or most recent revision) from the UN Population Division. Extract city-level population estimates for the most recent year available.

- [ ] **Step 2: Create the bundled CSV**

Filter to the top ~100 cities by metro area population. Write `resources/un_wup_cities.csv` with columns:

```csv
city,country_iso3,population,year,source
Tokyo,JPN,37400000,2024,UN World Urbanization Prospects 2024
Delhi,IND,32900000,2024,UN World Urbanization Prospects 2024
...
```

Only include cities whose `country_iso3` matches an entity in our ENTITIES list.

- [ ] **Step 3: Commit**

```bash
git add resources/un_wup_cities.csv
git commit -m "data: add UN WUP top-100 cities population data"
```

---

## Task 6: Deck Builder (`build_deck.py`)

**Files:**
- Create: `src/knowledge_base/build_deck.py`
- Create: `tests/test_build_deck.py`
- Create: `tests/fixtures/sample_gdp.csv`

- [ ] **Step 1: Create test fixtures**

`tests/fixtures/sample_gdp.csv`:
```csv
entity,entity_type,region,era,year,value,source
World,region,,current,2022,17500,World Bank WDI
South Asia,region,,current,2022,7200,World Bank WDI
India,major,South Asia,current,2022,8379,World Bank WDI
India,major,South Asia,1990,1990,1806,World Bank WDI
```

`tests/fixtures/sample_city_population.csv`:
```csv
entity,entity_type,region,era,year,value,source,city,country_population
India,major,South Asia,current,2024,32900000,UN World Urbanization Prospects 2024,Delhi,1400000000
Japan,major,East Asia & Pacific,current,2024,37400000,UN World Urbanization Prospects 2024,Tokyo,125000000
```

- [ ] **Step 2: Write card generation tests**

```python
# tests/test_build_deck.py
import polars as pl
import pytest
from pathlib import Path
from knowledge_base.build_deck import (
    generate_question,
    generate_notes,
    generate_notes_city,
    generate_notes_land_area,
    compute_reference_averages,
    build_tags,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_generate_question_with_units():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=2022,
        unit_label="in 2021 international dollars",
        era="current",
    )
    assert q == "What is India's GDP per capita (PPP) as of 2022, in 2021 international dollars?"


def test_generate_question_historical():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=1990,
        unit_label="in 2021 international dollars",
        era="1990",
    )
    assert q == "What was India's GDP per capita (PPP) in 1990, in 2021 international dollars?"


def test_generate_notes_country():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=7200,
        unit_prefix="$",
    )
    assert "World Bank WDI" in notes
    assert "World avg: $17,500" in notes
    assert "regional avg: $7,200" in notes


def test_generate_notes_region():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=None,
        unit_prefix="$",
    )
    assert "regional avg" not in notes
    assert "World avg: $17,500" in notes


def test_build_tags():
    tags = build_tags(
        category="development",
        indicator_id="gdp_pc_ppp",
        entity_slug="india",
        entity_type="major",
        era="current",
    )
    assert "category::development" in tags
    assert "indicator::gdp_pc_ppp" in tags
    assert "entity::india" in tags
    assert "entity_type::major" in tags
    assert "era::current" in tags


def test_compute_reference_averages():
    df = pl.read_csv(FIXTURES / "sample_gdp.csv")
    world_avg, region_avgs = compute_reference_averages(df, "current")
    assert world_avg == pytest.approx(17500)
    assert region_avgs["South Asia"] == pytest.approx(7200)


def test_generate_notes_city():
    notes = generate_notes_city(
        source="UN World Urbanization Prospects 2024",
        country_population=1_400_000_000,
    )
    assert "UN World Urbanization Prospects" in notes
    assert "Country population: 1,400,000,000" in notes


def test_generate_notes_land_area():
    notes = generate_notes_land_area(
        source="World Bank WDI",
        reference_total=30_370_000,
    )
    assert "World Bank WDI" in notes
    assert "30,370,000" in notes
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_build_deck.py -v
```

Expected: ImportError.

- [ ] **Step 4: Write build_deck.py**

Implement the deck builder:

1. `compute_reference_averages(df, era)` — extract World row as world_avg, region rows as region_avgs dict
2. `generate_question(entity, indicator_name, year, unit_label, era)` — produce the Front field. Use "What is...as of {year}" for current era, "What was...in {year}" for historical.
3. `generate_notes(source, world_avg, regional_avg, unit_prefix)` — produce the Notes field with source + reference class comparisons. Format large numbers with commas.
4. `generate_notes_land_area(source, reference_total)` — special Notes for land area cards (regional total or world total as reference).
5. `generate_notes_city(source, country_population)` — special Notes for city population cards (country total population as context).
6. `build_tags(category, indicator_id, entity_slug, entity_type, era)` — return list of tag strings.
7. `main(data_dir: Path = Path("data"), output_path: Path = Path("knowledge_base.apkg"))` — accepts optional data_dir and output_path so it works both as a CLI entry point (no args) and in tests (with overrides):
   - Read each CSV from `data_dir/`. Match CSV filename stems to indicator `id` fields in `INDICATORS` config to look up metadata (question template, unit label, category, tags).
   - For each indicator, compute reference averages
   - For each row, generate question, answer, notes, tags
   - Create genanki Note objects using model ID `1677887272395` with the verbatim card templates from the example deck
   - Add all notes to a genanki Deck named "Knowledge Base"
   - Write to `output_path`

The genanki Model definition must copy the exact `qfmt`, `afmt`, `css`, and field definitions from the example deck. These contain the scoring JavaScript. The full templates were extracted earlier in this project (see the `col` table's `models` JSON in the example `.apkg` at `resources/Anki_with_uncertainty__example_deck.apkg`). Store the template strings as constants in `build_deck.py` (they are ~4KB of HTML/JS each).

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_build_deck.py -v
```

Expected: all 8 pass.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/build_deck.py tests/test_build_deck.py tests/fixtures/sample_gdp.csv
git commit -m "feat: add deck builder with question generation and tagging"
```

---

## Task 7: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""End-to-end: fixture CSVs → .apkg file."""
from pathlib import Path

from knowledge_base.build_deck import main as build_main

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_deck_from_fixtures(tmp_path):
    """Build a deck from the test fixture CSVs and verify the .apkg is created."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Copy both fixtures
    for fixture_name, csv_name in [
        ("sample_gdp.csv", "gdp_pc_ppp.csv"),
        ("sample_city_population.csv", "city_population.csv"),
    ]:
        src = FIXTURES / fixture_name
        if src.exists():
            (data_dir / csv_name).write_text(src.read_text())

    output_path = tmp_path / "test_deck.apkg"

    build_main(data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it passes**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: PASS. The fixture CSV produces a valid .apkg.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test"
```

---

## Task 8: Live Data Fetch & Deck Generation

This is the first real run — fetch live data and produce the actual deck.

- [ ] **Step 1: Run fetch_data.py**

```bash
uv run fetch-data
```

Expected: CSVs written to `data/` — one per indicator. Print a summary of how many entity×era data points were found per indicator.

- [ ] **Step 2: Inspect the CSVs**

Spot-check a few CSVs for sanity:
- `data/gdp_pc_ppp.csv` — verify India 1960, 1990, current rows exist with reasonable values
- `data/life_expectancy.csv` — verify World, Sub-Saharan Africa rows exist
- `data/land_area.csv` — verify only one row per entity (no era dimension)

- [ ] **Step 3: Run build_deck.py**

```bash
uv run build-deck
```

Expected: `knowledge_base.apkg` written to project root. Print card count summary.

- [ ] **Step 4: Verify card count**

Expected: ~1,200–1,500 cards total. If significantly fewer, investigate data gaps. If significantly more, check for duplicates.

- [ ] **Step 5: Spot-check the .apkg**

Extract and inspect a few cards from the generated .apkg:

```bash
cd /tmp && mkdir -p deck_check && cd deck_check && rm -f * && \
unzip /home/cmf/Dropbox/Apps/knowledge-base/knowledge_base.apkg && \
sqlite3 collection.anki21 "SELECT flds FROM notes LIMIT 5"
```

Verify question format, answer values, and notes field look correct.

- [ ] **Step 6: Commit data fetch script outputs are not committed (gitignored), but verify .gitignore is working**

```bash
git status
```

Expected: `data/*.csv` and `knowledge_base.apkg` should not appear as untracked.

- [ ] **Step 7: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete v1 pipeline — fetch, build, and generate deck"
```
