# Descriptive Statistics Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new Anki deck that quizzes on the mean, median, standard deviation, and range of each indicator across all existing Knowledge Base decks, using Enhanced Cloze cards.

**Architecture:** Two-stage pipeline (`fetch-desc-stats` -> CSVs -> `build-deck descriptive_stats` -> `.apkg`). World Bank indicators use a full ~190-country cross-section from the API. Urban indicators compute stats from existing top-50-city CSVs. A new genanki model wraps the Enhanced Cloze 2.1 v2 note type.

**Tech Stack:** Python 3.12+, polars, httpx, genanki, pytest

---

### Task 1: Add `compute_desc_stats` helper with tests

**Files:**
- Create: `src/knowledge_base/desc_stats.py`
- Create: `tests/test_desc_stats.py`

This is the pure computation core — takes a polars DataFrame of values and returns a stats dict. Shared by both WB and urban paths.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_desc_stats.py`:

```python
import polars as pl
import pytest
from knowledge_base.desc_stats import compute_desc_stats


def test_compute_desc_stats_basic():
    df = pl.DataFrame({
        "entity": ["A", "B", "C", "D", "E"],
        "value": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 5
    assert stats["mean"] == pytest.approx(30.0)
    assert stats["median"] == pytest.approx(30.0)
    assert stats["std"] == pytest.approx(14.1421, rel=1e-3)
    assert stats["min_value"] == pytest.approx(10.0)
    assert stats["min_entity"] == "A"
    assert stats["max_value"] == pytest.approx(50.0)
    assert stats["max_entity"] == "E"


def test_compute_desc_stats_single_row():
    df = pl.DataFrame({
        "entity": ["A"],
        "value": [42.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 1
    assert stats["mean"] == pytest.approx(42.0)
    assert stats["median"] == pytest.approx(42.0)
    assert stats["std"] == pytest.approx(0.0)
    assert stats["min_entity"] == "A"
    assert stats["max_entity"] == "A"


def test_compute_desc_stats_two_rows():
    df = pl.DataFrame({
        "entity": ["A", "B"],
        "value": [100.0, 200.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 2
    assert stats["mean"] == pytest.approx(150.0)
    assert stats["median"] == pytest.approx(150.0)
    assert stats["min_value"] == pytest.approx(100.0)
    assert stats["max_value"] == pytest.approx(200.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_desc_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge_base.desc_stats'`

- [ ] **Step 3: Write the implementation**

Create `src/knowledge_base/desc_stats.py`:

```python
"""Compute descriptive statistics over a polars DataFrame of entity values."""

from __future__ import annotations

import polars as pl


def compute_desc_stats(df: pl.DataFrame) -> dict:
    """Compute mean, median, std, min, max over 'value' column.

    Args:
        df: Must have columns 'entity' and 'value'.

    Returns:
        Dict with keys: n, mean, median, std, min_value, min_entity,
        max_value, max_entity.
    """
    values = df["value"]
    n = len(values)

    mean = values.mean()
    median = values.median()
    std = values.std() if n > 1 else 0.0

    min_idx = values.arg_min()
    max_idx = values.arg_max()

    return {
        "n": n,
        "mean": mean,
        "median": median,
        "std": std,
        "min_value": values[min_idx],
        "min_entity": df["entity"][min_idx],
        "max_value": values[max_idx],
        "max_entity": df["entity"][max_idx],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_desc_stats.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/desc_stats.py tests/test_desc_stats.py
git commit -m "feat: add compute_desc_stats helper for descriptive statistics"
```

---

### Task 2: Add `descriptive_stats` deck config

**Files:**
- Modify: `src/knowledge_base/config.py` (append to `DECKS` dict, around line 972)

Minimal config entry — no `indicators` or `era_ranges` since the summary CSVs are self-describing.

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_config.py`:

```python
def test_descriptive_stats_deck_exists():
    from knowledge_base.config import DECKS
    cfg = DECKS["descriptive_stats"]
    assert cfg["name"] == "Knowledge Base::Descriptive Statistics"
    assert cfg["data_dir"] == "data/descriptive_stats"
    assert cfg["output"] == "knowledge_base_descriptive_stats.apkg"
    assert isinstance(cfg["deck_id"], int)
    assert "source_decks" in cfg
    assert "urban_areas" in cfg["source_decks"]
    assert "development" in cfg["source_decks"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_descriptive_stats_deck_exists -v`
Expected: FAIL — `KeyError: 'descriptive_stats'`

- [ ] **Step 3: Add the config entry**

In `src/knowledge_base/config.py`, add this entry at the end of the `DECKS` dict (before the closing `}`), after the `"urban_areas"` entry:

```python
    "descriptive_stats": {
        "name": "Knowledge Base::Descriptive Statistics",
        "deck_id": 2026032605,
        "output": "knowledge_base_descriptive_stats.apkg",
        "data_dir": "data/descriptive_stats",
        "source_decks": ["development", "tech_adoption", "conflict_security", "finance", "urban_areas"],
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: all tests pass

- [ ] **Step 5: Create data directory**

```bash
mkdir -p data/descriptive_stats
touch data/descriptive_stats/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/config.py data/descriptive_stats/.gitkeep tests/test_config.py
git commit -m "feat: add descriptive_stats deck config and data directory"
```

---

### Task 3: Add `fetch_desc_stats.py` — World Bank path

**Files:**
- Create: `src/knowledge_base/fetch_desc_stats.py`
- Create: `tests/test_fetch_desc_stats.py`

The fetch module computes descriptive stats for WB indicators by fetching the full ~190-country cross-section, and for urban indicators by reading existing CSVs. This task covers the WB path; Task 4 adds the urban path.

- [ ] **Step 1: Write the failing tests for WB stat computation**

Create `tests/test_fetch_desc_stats.py`:

```python
import polars as pl
import pytest
from pathlib import Path
from knowledge_base.fetch_desc_stats import (
    compute_wb_indicator_stats,
    STATS_COLUMNS,
    build_stats_dataframe,
)


def test_compute_wb_indicator_stats_from_records():
    """Given raw WB API records, compute stats for one indicator."""
    records = [
        {"country_code": "USA", "year": 2023, "value": 75000.0},
        {"country_code": "IND", "year": 2023, "value": 9000.0},
        {"country_code": "NGA", "year": 2022, "value": 5000.0},
        {"country_code": "CHN", "year": 2023, "value": 23000.0},
    ]
    # country_names maps ISO3 -> display name
    country_names = {
        "USA": "United States",
        "IND": "India",
        "NGA": "Nigeria",
        "CHN": "China",
    }
    stats = compute_wb_indicator_stats(records, country_names)
    assert stats["n"] == 4
    assert stats["mean"] == pytest.approx(28000.0)
    assert stats["min_value"] == pytest.approx(5000.0)
    assert stats["min_entity"] == "Nigeria"
    assert stats["max_value"] == pytest.approx(75000.0)
    assert stats["max_entity"] == "United States"
    assert isinstance(stats["year"], int)


def test_compute_wb_indicator_stats_picks_most_recent_per_country():
    """When a country has multiple years, pick the most recent."""
    records = [
        {"country_code": "USA", "year": 2020, "value": 60000.0},
        {"country_code": "USA", "year": 2023, "value": 75000.0},
        {"country_code": "IND", "year": 2022, "value": 9000.0},
    ]
    country_names = {"USA": "United States", "IND": "India"}
    stats = compute_wb_indicator_stats(records, country_names)
    assert stats["n"] == 2
    assert stats["max_value"] == pytest.approx(75000.0)


def test_build_stats_dataframe():
    row = {
        "indicator_id": "gdp_pc_ppp",
        "indicator_name": "GDP per capita (PPP)",
        "category": "development",
        "source_deck": "development",
        "unit_label": "in 2021 international dollars",
        "unit_prefix": "$",
        "decimals": 0,
        "scale_factor": 1,
        "year": 2023,
        "n": 190,
        "mean": 18000.0,
        "median": 13000.0,
        "std": 22000.0,
        "min_value": 800.0,
        "min_entity": "Burundi",
        "max_value": 140000.0,
        "max_entity": "Luxembourg",
    }
    df = build_stats_dataframe(row)
    assert set(df.columns) == set(STATS_COLUMNS)
    assert len(df) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetch_desc_stats.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/knowledge_base/fetch_desc_stats.py`:

```python
"""Fetch descriptive statistics for all indicators across Knowledge Base decks."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from knowledge_base.config import DECKS
from knowledge_base.desc_stats import compute_desc_stats
from knowledge_base.wb_api import fetch_indicator

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

STATS_COLUMNS = [
    "indicator_id", "indicator_name", "category", "source_deck", "unit_label",
    "unit_prefix", "decimals", "scale_factor", "year", "n", "mean",
    "median", "std", "min_value", "min_entity", "max_value", "max_entity",
]

WB_SOURCE_DECKS = ["development", "tech_adoption", "conflict_security", "finance"]

# ---------------------------------------------------------------------------
# World Bank helpers
# ---------------------------------------------------------------------------


def _fetch_all_country_codes() -> tuple[list[str], dict[str, str]]:
    """Return (list of all WB country ISO3 codes, {iso3: name} mapping).

    Uses the World Bank API country list endpoint.
    """
    import httpx
    from knowledge_base.wb_api import WB_API_BASE

    url = f"{WB_API_BASE}/country"
    params = {"format": "json", "per_page": 500}
    resp = httpx.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    codes = []
    names = {}
    for entry in data[1]:
        # Skip aggregates (region, lending type, etc.)
        if entry["region"]["id"] == "NA":
            continue
        iso3 = entry["id"]
        codes.append(iso3)
        names[iso3] = entry["name"]
    return codes, names


def compute_wb_indicator_stats(
    records: list[dict],
    country_names: dict[str, str],
) -> dict:
    """Compute descriptive stats from raw WB API records.

    Picks the most recent year per country, then computes stats.
    Returns dict with keys: n, mean, median, std, min_value, min_entity,
    max_value, max_entity, year.
    """
    # Pick most recent record per country
    best: dict[str, dict] = {}
    for r in records:
        code = r["country_code"]
        if code not in best or r["year"] > best[code]["year"]:
            best[code] = r

    if not best:
        return None

    # Build DataFrame for compute_desc_stats
    rows = []
    years = []
    for code, rec in best.items():
        name = country_names.get(code, code)
        rows.append({"entity": name, "value": float(rec["value"])})
        years.append(rec["year"])

    df = pl.DataFrame(rows)
    stats = compute_desc_stats(df)
    # Use the most common year as the representative year
    stats["year"] = max(set(years), key=years.count)
    return stats


def build_stats_dataframe(row: dict) -> pl.DataFrame:
    """Build a single-row polars DataFrame from a stats dict."""
    return pl.DataFrame(
        [{col: row.get(col) for col in STATS_COLUMNS}],
        schema={
            "indicator_id": pl.Utf8,
            "indicator_name": pl.Utf8,
            "category": pl.Utf8,
            "source_deck": pl.Utf8,
            "unit_label": pl.Utf8,
            "unit_prefix": pl.Utf8,
            "decimals": pl.Int64,
            "scale_factor": pl.Int64,
            "year": pl.Int64,
            "n": pl.Int64,
            "mean": pl.Float64,
            "median": pl.Float64,
            "std": pl.Float64,
            "min_value": pl.Float64,
            "min_entity": pl.Utf8,
            "max_value": pl.Float64,
            "max_entity": pl.Utf8,
        },
    )


# ---------------------------------------------------------------------------
# WB fetch orchestrator
# ---------------------------------------------------------------------------


def fetch_wb_stats(output_dir: Path) -> None:
    """Fetch full cross-section stats for all WB indicators and write CSVs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    all_codes, country_names = _fetch_all_country_codes()

    for deck_key in WB_SOURCE_DECKS:
        deck = DECKS[deck_key]
        era_ranges = deck["era_ranges"]
        year_start, year_end, _ = era_ranges["current"]

        for indicator in deck["indicators"]:
            indicator_id = indicator["id"]
            print(f"  [{deck_key}] {indicator_id}...")

            try:
                records = fetch_indicator(
                    indicator["wb_code"], all_codes, year_start, year_end
                )
            except Exception as exc:
                print(f"    ERROR fetching {indicator_id}: {exc}")
                continue

            stats = compute_wb_indicator_stats(records, country_names)
            if stats is None:
                print(f"    No data for {indicator_id}")
                continue

            row = {
                **stats,
                "indicator_id": indicator_id,
                "indicator_name": indicator["name"],
                "category": indicator["category"],
                "source_deck": deck_key,
                "unit_label": indicator["unit_label"],
                "unit_prefix": indicator.get("unit_prefix", ""),
                "decimals": indicator.get("decimals", 1),
                "scale_factor": indicator.get("scale_factor", 1),
            }
            df = build_stats_dataframe(row)
            out_path = output_dir / f"{indicator_id}.csv"
            df.write_csv(out_path)
            print(f"    wrote {out_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetch_desc_stats.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/fetch_desc_stats.py tests/test_fetch_desc_stats.py
git commit -m "feat: add fetch_desc_stats WB path with stats computation"
```

---

### Task 4: Add `fetch_desc_stats.py` — Urban path

**Files:**
- Modify: `src/knowledge_base/fetch_desc_stats.py`
- Modify: `tests/test_fetch_desc_stats.py`

Reads existing `data/urban_areas/*.csv`, filters to city rows and most recent era, computes stats, writes CSVs prefixed with `urban_`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fetch_desc_stats.py`:

```python
from knowledge_base.fetch_desc_stats import compute_urban_indicator_stats


def test_compute_urban_indicator_stats(tmp_path):
    """Compute stats from a sample urban CSV."""
    csv_content = (
        "entity,entity_type,region,era,year,value,source\n"
        "All Cities,aggregate,,2020,2020,15000000,GHS-UCDB R2024A\n"
        "High income,aggregate,,2020,2020,20000000,GHS-UCDB R2024A\n"
        "CityA,city,,2020,2020,10000000,GHS-UCDB R2024A\n"
        "CityB,city,,2020,2020,20000000,GHS-UCDB R2024A\n"
        "CityC,city,,2020,2020,30000000,GHS-UCDB R2024A\n"
        "CityA,city,,2010,2010,8000000,GHS-UCDB R2024A\n"
    )
    csv_path = tmp_path / "population.csv"
    csv_path.write_text(csv_content)

    stats = compute_urban_indicator_stats(csv_path)
    assert stats["n"] == 3
    assert stats["mean"] == pytest.approx(20000000.0)
    assert stats["min_entity"] == "CityA"
    assert stats["max_entity"] == "CityC"
    assert stats["year"] == 2020


def test_compute_urban_indicator_stats_picks_latest_era(tmp_path):
    """When multiple eras exist, use only the most recent."""
    csv_content = (
        "entity,entity_type,region,era,year,value,source\n"
        "CityA,city,,2010,2010,5000.0,GHS-UCDB R2024A\n"
        "CityB,city,,2010,2010,6000.0,GHS-UCDB R2024A\n"
        "CityA,city,,2020,2020,8000.0,GHS-UCDB R2024A\n"
        "CityB,city,,2020,2020,9000.0,GHS-UCDB R2024A\n"
    )
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(csv_content)

    stats = compute_urban_indicator_stats(csv_path)
    assert stats["n"] == 2
    assert stats["mean"] == pytest.approx(8500.0)
    assert stats["year"] == 2020
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetch_desc_stats.py::test_compute_urban_indicator_stats tests/test_fetch_desc_stats.py::test_compute_urban_indicator_stats_picks_latest_era -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `src/knowledge_base/fetch_desc_stats.py`:

```python
# ---------------------------------------------------------------------------
# Urban helpers
# ---------------------------------------------------------------------------


def compute_urban_indicator_stats(csv_path: Path) -> dict | None:
    """Compute stats from an existing urban indicator CSV.

    Filters to city rows (excludes aggregates) and the most recent era.
    Returns stats dict with year, or None if no city data found.
    """
    df = pl.read_csv(csv_path)

    # Filter to city rows only
    cities = df.filter(pl.col("entity_type") == "city")
    if len(cities) == 0:
        return None

    # Pick the most recent era
    latest_era = cities["era"].cast(pl.Utf8).sort(descending=True).first()
    cities = cities.filter(pl.col("era") == latest_era)

    stats = compute_desc_stats(cities.select(["entity", "value"]))
    stats["year"] = int(cities["year"][0])
    return stats


# ---------------------------------------------------------------------------
# Urban fetch orchestrator
# ---------------------------------------------------------------------------


def fetch_urban_stats(output_dir: Path) -> None:
    """Compute stats for all urban indicators from existing CSVs."""
    urban_cfg = DECKS["urban_areas"]
    urban_data_dir = Path(urban_cfg["data_dir"])

    if not urban_data_dir.exists():
        print(f"  Urban data dir {urban_data_dir} not found — skipping.")
        print("  Run 'fetch-urban-data' first.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    for indicator in urban_cfg["indicators"]:
        indicator_id = indicator["id"]
        csv_path = urban_data_dir / f"{indicator_id}.csv"
        if not csv_path.exists():
            print(f"  [urban_areas] {indicator_id} — CSV not found, skipping")
            continue

        print(f"  [urban_areas] {indicator_id}...")

        stats = compute_urban_indicator_stats(csv_path)
        if stats is None:
            print(f"    No city data for {indicator_id}")
            continue

        row = {
            **stats,
            "indicator_id": f"urban_{indicator_id}",
            "indicator_name": indicator["name"],
            "category": indicator["category"],
            "source_deck": "urban_areas",
            "unit_label": indicator["unit_label"],
            "unit_prefix": indicator.get("unit_prefix", ""),
            "decimals": indicator.get("decimals", 1),
            "scale_factor": indicator.get("scale_factor", 1),
        }
        df = build_stats_dataframe(row)
        out_path = output_dir / f"urban_{indicator_id}.csv"
        df.write_csv(out_path)
        print(f"    wrote {out_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetch_desc_stats.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/fetch_desc_stats.py tests/test_fetch_desc_stats.py
git commit -m "feat: add fetch_desc_stats urban path"
```

---

### Task 5: Add CLI entry point and `_run` orchestrator

**Files:**
- Modify: `src/knowledge_base/fetch_desc_stats.py`
- Modify: `pyproject.toml`

Wire up `fetch_wb_stats` + `fetch_urban_stats` into a `_run` function and expose as `fetch-desc-stats` CLI entry point.

- [ ] **Step 1: Add `_run` and `main` to `fetch_desc_stats.py`**

Add to the bottom of `src/knowledge_base/fetch_desc_stats.py`:

```python
# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def _run(output_dir: Path | None = None) -> None:
    """Fetch descriptive stats for all indicators and write CSVs."""
    desc_cfg = DECKS["descriptive_stats"]
    resolved_dir = output_dir or Path(desc_cfg["data_dir"])

    print("Fetching World Bank indicator stats...")
    fetch_wb_stats(resolved_dir)

    print("Computing urban indicator stats...")
    fetch_urban_stats(resolved_dir)

    print("Done.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for fetch-desc-stats."""
    _run()
```

- [ ] **Step 2: Add entry point to `pyproject.toml`**

In `pyproject.toml`, add to `[project.scripts]`:

```toml
fetch-desc-stats = "knowledge_base.fetch_desc_stats:main"
```

So the full section reads:

```toml
[project.scripts]
fetch-data = "knowledge_base.fetch_data:main"
fetch-urban-data = "knowledge_base.fetch_urban_data:main"
fetch-desc-stats = "knowledge_base.fetch_desc_stats:main"
build-deck = "knowledge_base.build_deck:main"
```

- [ ] **Step 3: Sync dependencies**

Run: `uv sync`

- [ ] **Step 4: Verify entry point is registered**

Run: `uv run fetch-desc-stats --help 2>&1 || true`
Expected: Runs without `ModuleNotFoundError` (will attempt to fetch data and likely succeed or print status)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/fetch_desc_stats.py pyproject.toml
git commit -m "feat: add fetch-desc-stats CLI entry point"
```

---

### Task 6: Add Enhanced Cloze model and card generation in `build_deck.py`

**Files:**
- Modify: `src/knowledge_base/build_deck.py`
- Modify: `tests/test_build_deck.py`

Add the Enhanced Cloze genanki model, the cloze content generator, and the `_run_descriptive_stats` build function. The template HTML/CSS is loaded from the Enhanced Cloze add-on's installed files.

- [ ] **Step 1: Write failing tests for cloze content generation**

Add to `tests/test_build_deck.py`:

```python
from knowledge_base.build_deck import generate_cloze_content, generate_desc_stats_note_field


def test_generate_cloze_content_wb():
    row = {
        "indicator_name": "GDP per capita (PPP)",
        "source_deck": "development",
        "unit_label": "in 2021 international dollars",
        "unit_prefix": "$",
        "decimals": 0,
        "scale_factor": 1,
        "year": 2024,
        "n": 190,
        "mean": 18463.0,
        "median": 13178.0,
        "std": 22147.0,
        "min_value": 878.0,
        "min_entity": "Burundi",
        "max_value": 143314.0,
        "max_entity": "Luxembourg",
    }
    content = generate_cloze_content(row)
    assert "190 countries" in content
    assert "GDP per capita (PPP)" in content
    assert "2024" in content
    assert "{{c1::" in content
    assert "{{c2::" in content
    assert "{{c3::" in content
    assert "{{c4::" in content
    assert "{{c5::" in content
    assert "Burundi" in content
    assert "Luxembourg" in content
    assert "$878" in content or "$878" in content


def test_generate_cloze_content_urban():
    row = {
        "indicator_name": "CO2 emissions per capita",
        "source_deck": "urban_areas",
        "unit_label": "tonnes per person",
        "unit_prefix": "",
        "decimals": 2,
        "scale_factor": 1,
        "year": 2020,
        "n": 50,
        "mean": 6.78,
        "median": 5.12,
        "std": 4.89,
        "min_value": 1.23,
        "min_entity": "Kinshasa",
        "max_value": 18.45,
        "max_entity": "Houston",
    }
    content = generate_cloze_content(row)
    assert "top 50 cities" in content
    assert "CO2 emissions per capita" in content
    assert "Kinshasa" in content
    assert "Houston" in content


def test_generate_desc_stats_note_field_wb():
    note = generate_desc_stats_note_field("development")
    assert "World Bank WDI" in note


def test_generate_desc_stats_note_field_urban():
    note = generate_desc_stats_note_field("urban_areas")
    assert "GHS-UCDB" in note
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_deck.py::test_generate_cloze_content_wb tests/test_build_deck.py::test_generate_cloze_content_urban tests/test_build_deck.py::test_generate_desc_stats_note_field_wb tests/test_build_deck.py::test_generate_desc_stats_note_field_urban -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

Add these functions and the model definition to `src/knowledge_base/build_deck.py`.

After the existing `INTERVAL_MODEL` definition (around line 275), add:

```python
# ---------------------------------------------------------------------------
# Enhanced Cloze model (for descriptive statistics deck)
# ---------------------------------------------------------------------------

ENHANCED_CLOZE_ADDON_DIR = Path.home() / ".local/share/Anki2/addons21/1990296174/note_type"

def _load_enhanced_cloze_model() -> genanki.Model:
    """Load the Enhanced Cloze 2.1 v2 model from the installed add-on."""
    front_path = ENHANCED_CLOZE_ADDON_DIR / "Enhanced_Cloze_Front_Side.html"
    back_path = ENHANCED_CLOZE_ADDON_DIR / "Enhanced_Cloze_Back_Side.html"
    css_path = ENHANCED_CLOZE_ADDON_DIR / "Enhanced_Cloze_CSS.css"

    for p in (front_path, back_path, css_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Enhanced Cloze template not found: {p}\n"
                "Install the Enhanced Cloze add-on (1990296174) in Anki first."
            )

    return genanki.Model(
        1774552435321,
        "Enhanced Cloze 2.1 v2",
        model_type=1,  # cloze
        fields=[
            {"name": "Content"},
            {"name": "Note"},
            {"name": "Mnemonics"},
            {"name": "Extra"},
            {"name": "Cloze99"},
        ],
        templates=[
            {
                "name": "Enhanced Cloze",
                "qfmt": front_path.read_text(),
                "afmt": back_path.read_text(),
            }
        ],
        css=css_path.read_text(),
    )
```

Add the content generation functions (before `_run`):

```python
def _format_stat(value: float, unit_prefix: str, decimals: int, scale_factor: int) -> str:
    """Format a stat value with prefix, scaling, and commas."""
    scaled = value / scale_factor
    if decimals == 0:
        return f"{unit_prefix}{scaled:,.0f}"
    return f"{unit_prefix}{scaled:,.{decimals}f}"


def generate_cloze_content(row: dict) -> str:
    """Generate Enhanced Cloze content for a descriptive stats card."""
    name = row["indicator_name"]
    year = row["year"]
    n = row["n"]
    prefix = row["unit_prefix"]
    decimals = row["decimals"]
    sf = row["scale_factor"]

    fmt_min = _format_stat(row["min_value"], prefix, decimals, sf)
    fmt_max = _format_stat(row["max_value"], prefix, decimals, sf)
    fmt_mean = _format_stat(row["mean"], prefix, decimals, sf)
    fmt_median = _format_stat(row["median"], prefix, decimals, sf)
    fmt_std = _format_stat(row["std"], prefix, decimals, sf)

    if row["source_deck"] == "urban_areas":
        population = f"top {n} cities"
    else:
        population = f"{n} countries"

    return (
        f"Across all {population}, {name} as of {year} "
        f"ranges from {{{{c1::{fmt_min}}}}} ({row['min_entity']}) "
        f"to {{{{c2::{fmt_max}}}}} ({row['max_entity']}), "
        f"with a mean of {{{{c3::{fmt_mean}}}}}, "
        f"median of {{{{c4::{fmt_median}}}}}, "
        f"and standard deviation of {{{{c5::{fmt_std}}}}}."
    )


def generate_desc_stats_note_field(source_deck: str) -> str:
    """Generate the Note field for a descriptive stats card."""
    if source_deck == "urban_areas":
        return "Source: GHS-UCDB R2024A"
    return "Source: World Bank WDI"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_deck.py -v`
Expected: all tests pass (existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/build_deck.py tests/test_build_deck.py
git commit -m "feat: add Enhanced Cloze model and cloze content generators"
```

---

### Task 7: Add `_run_descriptive_stats` build function and dispatch

**Files:**
- Modify: `src/knowledge_base/build_deck.py`
- Modify: `tests/test_integration.py`

Wire up the build path: read summary CSVs, generate Enhanced Cloze notes, write `.apkg`. Update `_run` to dispatch to `_run_descriptive_stats` when the deck key is `descriptive_stats`.

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_integration.py`:

```python
def test_build_descriptive_stats_deck(tmp_path):
    """End-to-end: summary CSV → .apkg for descriptive stats deck."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    header = (
        "indicator_id,indicator_name,category,source_deck,unit_label,unit_prefix,"
        "decimals,scale_factor,year,n,mean,median,std,"
        "min_value,min_entity,max_value,max_entity\n"
    )
    (data_dir / "gdp_pc_ppp.csv").write_text(
        header
        + "gdp_pc_ppp,GDP per capita (PPP),development,development,"
        "in 2021 international dollars,$,0,1,2024,190,"
        "18463.0,13178.0,22147.0,878.0,Burundi,143314.0,Luxembourg\n"
    )
    (data_dir / "urban_population.csv").write_text(
        header
        + "urban_population,Population,demographics,urban_areas,"
        "millions,,1,1000000,2025,50,"
        "12895864.0,10500000.0,8000000.0,1200000.0,Luanda,38000000.0,Tokyo\n"
    )

    output_path = tmp_path / "test_desc_stats.apkg"

    _run("descriptive_stats", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_integration.py::test_build_descriptive_stats_deck -v`
Expected: FAIL — `_run` doesn't handle `descriptive_stats` key

- [ ] **Step 3: Write `_run_descriptive_stats`**

Add to `src/knowledge_base/build_deck.py`, before `_run`:

```python
def _run_descriptive_stats(
    data_dir: Path | None = None,
    output_path: Path | None = None,
) -> None:
    """Build the descriptive statistics deck from summary CSVs."""
    deck_cfg = DECKS["descriptive_stats"]
    resolved_data_dir = data_dir or Path(deck_cfg["data_dir"])
    resolved_output_path = output_path or Path(deck_cfg["output"])

    model = _load_enhanced_cloze_model()
    deck = genanki.Deck(deck_cfg["deck_id"], deck_cfg["name"])

    csv_files = sorted(resolved_data_dir.glob("*.csv"))

    for csv_path in csv_files:
        df = pl.read_csv(csv_path)
        if len(df) == 0:
            continue

        row = df.row(0, named=True)

        content = generate_cloze_content(row)
        note_field = generate_desc_stats_note_field(row["source_deck"])

        tags = [
            f"source_deck::{row['source_deck']}",
            f"category::{row['category']}",
        ]

        note = genanki.Note(
            model=model,
            fields=[
                content,      # Content
                note_field,   # Note
                "",           # Mnemonics
                "",           # Extra
                "",           # Cloze99
            ],
            tags=tags,
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    package.write_to_file(str(resolved_output_path))
```

- [ ] **Step 4: Update `_run` to dispatch**

Modify the existing `_run` function. At the top of the function, after the `deck_key not in DECKS` check, add:

```python
    if deck_key == "descriptive_stats":
        _run_descriptive_stats(data_dir=data_dir, output_path=output_path)
        return
```

The `_run` function signature already accepts `data_dir` and `output_path` as the second and third args, so this works directly.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_integration.py -v`
Expected: all integration tests pass (existing + new)

Then run the full suite:

Run: `uv run pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/build_deck.py tests/test_integration.py
git commit -m "feat: add _run_descriptive_stats build path with dispatch"
```

---

### Task 8: Update CLAUDE.md and run end-to-end

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

In the Quick Reference section, add the new entry point:

```bash
uv run fetch-desc-stats              # compute stats from WB API + urban CSVs → data/descriptive_stats/*.csv
```

In the "Available deck keys" line, add `descriptive_stats`:

```
Available deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`, `urban_areas`, `descriptive_stats`
```

In the "Adding a New Deck" section, no changes needed — `descriptive_stats` follows a different pattern and is already documented by its own spec.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with descriptive statistics deck"
```

- [ ] **Step 4: Run end-to-end (optional, requires network)**

This step actually fetches from the World Bank API and builds the deck. It requires the urban CSVs to already exist (`uv run fetch-urban-data` must have been run).

```bash
uv run fetch-desc-stats
uv run build-deck descriptive_stats
```

Verify:
- `data/descriptive_stats/` contains one CSV per indicator (~40 WB + 6 urban)
- `knowledge_base_descriptive_stats.apkg` exists and has non-zero size
- Import into Anki and confirm cards display correctly with Enhanced Cloze behavior
