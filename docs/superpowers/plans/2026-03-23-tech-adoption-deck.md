# Technology Adoption Deck + Deck Registry Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the pipeline to support multiple decks via a `DECKS` registry in config.py, then add a Technology Adoption deck with 6 WB WDI indicators across 4 decade-interval eras.

**Architecture:** `config.py` gets a `DECKS` dict keyed by deck name. `fetch_data.py` and `build_deck.py` take a deck key argument via `sys.argv[1]`. Existing development deck behavior is preserved. The tech adoption deck reuses the same 47 entities and the full shared infrastructure (wb_api, card templates, tag generation).

**Tech Stack:** Python 3.12+, uv, genanki, httpx, polars (all existing)

**Spec:** `docs/superpowers/specs/2026-03-23-tech-adoption-deck-design.md`

---

## File Structure

```
src/knowledge_base/
    config.py        # MODIFIED: DECKS registry replaces top-level ERA_RANGES/INDICATORS
    fetch_data.py    # MODIFIED: main(deck_key), select_best_year_for_era gets era_ranges param
    build_deck.py    # MODIFIED: main(deck_key), remove ANSWER_DECIMALS/UNIT_PREFIX/DECK globals
    wb_api.py        # UNCHANGED
tests/
    test_config.py       # MODIFIED: access indicators/eras via DECKS
    test_fetch_data.py   # MODIFIED: pass era_ranges to select_best_year_for_era
    test_build_deck.py   # UNCHANGED (public function signatures don't change)
    test_integration.py  # MODIFIED: pass deck_key to build_main
data/
    development/     # NEW: moved from data/*.csv
    tech_adoption/   # NEW
```

No new files are created (except data subdirectories). This is purely a refactor of existing code plus new config entries.

---

## Task 1: Migrate config.py to DECKS registry

**Files:**
- Modify: `src/knowledge_base/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Update test_config.py for DECKS structure**

Replace the contents of `tests/test_config.py` with:

```python
from knowledge_base.config import DECKS, ENTITIES, REGIONS


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


def test_all_decks_have_required_fields():
    for key, deck in DECKS.items():
        assert "name" in deck, f"deck {key} missing name"
        assert "deck_id" in deck, f"deck {key} missing deck_id"
        assert "output" in deck, f"deck {key} missing output"
        assert "data_dir" in deck, f"deck {key} missing data_dir"
        assert "era_ranges" in deck, f"deck {key} missing era_ranges"
        assert "indicators" in deck, f"deck {key} missing indicators"


def test_all_indicators_have_required_fields():
    for key, deck in DECKS.items():
        for ind in deck["indicators"]:
            assert "id" in ind, f"deck {key}: indicator missing id"
            assert "name" in ind, f"deck {key}: {ind.get('id')} missing name"
            assert "category" in ind
            assert "unit_label" in ind
            assert "decimals" in ind, f"deck {key}: {ind['id']} missing decimals"
            assert "unit_prefix" in ind, f"deck {key}: {ind['id']} missing unit_prefix"
            assert "wb_code" in ind or ind["id"] == "city_population"


def test_region_names_consistent():
    region_names = {e["name"] for e in ENTITIES if e["entity_type"] == "region"}
    for e in ENTITIES:
        if e["entity_type"] != "region" and "region" in e:
            assert e["region"] in region_names, (
                f"{e['name']}'s region '{e['region']}' not in regions"
            )


def test_entity_count():
    assert 45 <= len(ENTITIES) <= 55


def test_era_ranges_format():
    for key, deck in DECKS.items():
        for era, rng in deck["era_ranges"].items():
            assert len(rng) == 3, f"deck {key} era {era}: expected 3-tuple"
            assert rng[0] <= rng[2] <= rng[1]


def test_development_deck_exists():
    assert "development" in DECKS
    assert len(DECKS["development"]["indicators"]) == 14


def test_tech_adoption_deck_exists():
    assert "tech_adoption" in DECKS
    assert len(DECKS["tech_adoption"]["indicators"]) == 6
    eras = DECKS["tech_adoption"]["era_ranges"]
    assert "1990" in eras
    assert "2000" in eras
    assert "2010" in eras
    assert "current" in eras
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError on `DECKS`, missing `decimals`/`unit_prefix` fields.

- [ ] **Step 3: Rewrite config.py with DECKS registry**

Replace the top-level `ERA_RANGES` and `INDICATORS` with a `DECKS` dict. Keep `ENTITIES` and `REGIONS` top-level. Each indicator dict gains `decimals` and `unit_prefix` fields.

The development deck's indicators are the existing 14, with these `decimals`/`unit_prefix` additions:

| id | decimals | unit_prefix |
|----|----------|-------------|
| gdp_pc_ppp | 0 | "$" |
| poverty_headcount | 1 | "" |
| gini | 1 | "" |
| trade_pct_gdp | 1 | "" |
| life_expectancy | 1 | "" |
| under5_mortality | 1 | "" |
| maternal_mortality | 1 | "" |
| fertility_rate | 2 | "" |
| co2_per_capita | 2 | "" |
| renewable_electricity | 1 | "" |
| energy_intensity | 1 | "" |
| population | 0 | "" |
| land_area | 0 | "" |
| city_population | 0 | "" |

The tech_adoption deck:

```python
"tech_adoption": {
    "name": "Knowledge Base::Technology Adoption",
    "deck_id": 2026032301,
    "output": "knowledge_base_tech_adoption.apkg",
    "data_dir": "data/tech_adoption",
    "era_ranges": {
        "1990": (1988, 1992, 1990),
        "2000": (1998, 2002, 2000),
        "2010": (2008, 2012, 2010),
        "current": (2020, 2026, 2026),
    },
    "indicators": [
        {
            "id": "internet_users",
            "name": "Internet users",
            "category": "technology",
            "unit_label": "% of population",
            "wb_code": "IT.NET.USER.ZS",
            "decimals": 1,
            "unit_prefix": "",
            "time_invariant": False,
            "current_only": False,
            "has_regional_aggregates": True,
        },
        # ... 5 more indicators as in the spec
    ],
},
```

Development deck keeps `"output": "knowledge_base.apkg"` for backward compatibility.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Move data directory and update .gitignore**

Move existing CSVs to the development subdirectory so `data_dir: "data/development"` works immediately:

```bash
mkdir -p data/development data/tech_adoption
mv data/*.csv data/development/ 2>/dev/null || true
rm -f data/.gitkeep
touch data/development/.gitkeep data/tech_adoption/.gitkeep
```

Update `.gitignore`: replace `data/*.csv` with `data/**/*.csv`.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py .gitignore data/development/.gitkeep data/tech_adoption/.gitkeep
git rm --cached data/.gitkeep 2>/dev/null || true
git commit -m "refactor: migrate config to DECKS registry, add tech_adoption deck, split data dirs"
```

---

## Task 2: Refactor fetch_data.py for multi-deck

**Files:**
- Modify: `src/knowledge_base/fetch_data.py`
- Modify: `tests/test_fetch_data.py`

- [ ] **Step 1: Update tests for new select_best_year_for_era signature**

The function now takes an explicit `era_ranges` dict instead of reading the global. Update all test calls:

```python
from knowledge_base.config import DECKS
from knowledge_base.fetch_data import (
    select_best_year_for_era,
    build_indicator_dataframe,
    EXPECTED_COLUMNS,
)

DEV_ERA_RANGES = DECKS["development"]["era_ranges"]


def test_select_best_year_for_era_prefers_target():
    records = [
        {"country_code": "IND", "year": 1958, "value": 100},
        {"country_code": "IND", "year": 1960, "value": 110},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best["year"] == 1960


def test_select_best_year_for_era_picks_closest():
    records = [
        {"country_code": "IND", "year": 1956, "value": 100},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best["year"] == 1963


def test_select_best_year_for_era_returns_none_outside_range():
    records = [
        {"country_code": "IND", "year": 1950, "value": 100},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best is None


def test_select_best_year_for_current_era():
    records = [
        {"country_code": "IND", "year": 2020, "value": 100},
        {"country_code": "IND", "year": 2022, "value": 110},
        {"country_code": "IND", "year": 2023, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "current", DEV_ERA_RANGES)
    assert best["year"] == 2023


def test_build_indicator_dataframe_columns():
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

Expected: TypeError — `select_best_year_for_era` doesn't accept `era_ranges` yet.

- [ ] **Step 3: Refactor fetch_data.py**

Key changes:
1. Remove `from knowledge_base.config import ERA_RANGES, INDICATORS` — replace with `from knowledge_base.config import DECKS, ENTITIES`
2. `select_best_year_for_era(records, country_code, era, era_ranges)` — add `era_ranges` parameter, use it instead of global
3. `main()` becomes a CLI wrapper that reads `sys.argv[1]`:

```python
def _run(deck_key: str, output_dir: Path | None = None) -> None:
    """Fetch all indicators for a deck and write CSV files."""
    if deck_key not in DECKS:
        print(f"Unknown deck: {deck_key}. Available: {', '.join(DECKS)}")
        raise SystemExit(1)

    deck = DECKS[deck_key]
    era_ranges = deck["era_ranges"]
    indicators = deck["indicators"]
    data_dir = Path(output_dir or deck["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)

    year_start = min(start for start, _, _ in era_ranges.values())
    year_end = max(end for _, end, _ in era_ranges.values())

    # ... rest of fetch logic, using era_ranges and indicators from deck
```

```python
def main() -> None:
    """CLI entry point."""
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: fetch-data <deck_key>")
        print(f"Available decks: {', '.join(DECKS)}")
        raise SystemExit(1)
    _run(sys.argv[1])
```

4. `_handle_city_population` takes `output_dir` as before (only called for development deck)
5. Pass `era_ranges` to `select_best_year_for_era` calls
6. Use `list(era_ranges.keys())` instead of `list(ERA_RANGES.keys())`

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_fetch_data.py -v
```

Expected: all 5 pass.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass (some test_config tests may need the config changes from Task 1).

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/fetch_data.py tests/test_fetch_data.py
git commit -m "refactor: fetch_data takes deck_key, select_best_year_for_era takes era_ranges"
```

---

## Task 3: Refactor build_deck.py for multi-deck

**Files:**
- Modify: `src/knowledge_base/build_deck.py`
- Modify: `tests/test_build_deck.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Update test_integration.py for new signature**

```python
"""End-to-end: fixture CSVs → .apkg file."""
from pathlib import Path
from unittest.mock import patch

from knowledge_base.build_deck import _run

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_deck_from_fixtures(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    for fixture_name, csv_name in [
        ("sample_gdp.csv", "gdp_pc_ppp.csv"),
        ("sample_city_population.csv", "city_population.csv"),
    ]:
        src = FIXTURES / fixture_name
        if src.exists():
            (data_dir / csv_name).write_text(src.read_text())

    output_path = tmp_path / "test_deck.apkg"

    _run("development", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
```

- [ ] **Step 2: Update test_build_deck.py**

The `format_answer` function now takes an indicator dict instead of indicator_id. But since it's an internal detail, the public function signatures for `generate_question`, `generate_notes`, `build_tags`, `compute_reference_averages` don't change. The existing tests remain valid. No changes needed to `test_build_deck.py`.

- [ ] **Step 3: Refactor build_deck.py**

Key changes:
1. Remove `from knowledge_base.config import INDICATORS` — replace with `from knowledge_base.config import DECKS`
2. Remove module-level `UNIT_PREFIX`, `ANSWER_DECIMALS`, `DECK`, `_INDICATOR_BY_ID`
3. `format_answer(value, indicator)` takes an indicator dict, reads `indicator["decimals"]`
4. Add `_run(deck_key, data_dir=None, output_path=None)` as the core logic:

```python
def _run(
    deck_key: str,
    data_dir: Path | None = None,
    output_path: Path | None = None,
) -> None:
    if deck_key not in DECKS:
        print(f"Unknown deck: {deck_key}. Available: {', '.join(DECKS)}")
        raise SystemExit(1)

    deck_cfg = DECKS[deck_key]
    indicator_by_id = {ind["id"]: ind for ind in deck_cfg["indicators"]}
    data_dir = data_dir or Path(deck_cfg["data_dir"])
    output_path = output_path or Path(deck_cfg["output"])

    deck = genanki.Deck(deck_cfg["deck_id"], deck_cfg["name"])
    # ... rest of card generation logic
```

5. `main()` becomes CLI wrapper:

```python
def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: build-deck <deck_key>")
        print(f"Available decks: {', '.join(DECKS)}")
        raise SystemExit(1)
    _run(sys.argv[1])
```

6. In the card generation loop, update ALL three sites that reference the removed globals:
   - `unit_prefix = UNIT_PREFIX.get(indicator_id, "")` (line 479) → `unit_prefix = indicator.get("unit_prefix", "")`
   - `format_answer(value, indicator_id)` (line 576) → `format_answer(value, indicator)` (pass the dict)
   - `decimals=ANSWER_DECIMALS.get(indicator_id, 1)` in `generate_notes` call (line 559) → `decimals=indicator.get("decimals", 1)`
7. Clean up `_find_entity_config`: move the deferred `from knowledge_base.config import ENTITIES` to the module-level import (alongside `DECKS`).

- [ ] **Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/build_deck.py tests/test_build_deck.py tests/test_integration.py
git commit -m "refactor: build_deck takes deck_key, remove global ANSWER_DECIMALS/UNIT_PREFIX"
```

---

## Task 4: Fetch and build the Technology Adoption deck

- [ ] **Step 1: Fetch tech adoption data**

```bash
uv run fetch-data tech_adoption
```

Expected: 6 CSVs written to `data/tech_adoption/`. Print row counts per indicator.

- [ ] **Step 2: Spot-check CSVs**

- `data/tech_adoption/internet_users.csv` — verify India has rows for 2000, 2010, current. 1990 may be missing.
- `data/tech_adoption/mobile_subscriptions.csv` — verify South Korea has high values (>100 per 100 people) in current era.
- `data/tech_adoption/rd_expenditure.csv` — expect fewer rows (sparse for developing countries).

- [ ] **Step 3: Build tech adoption deck**

```bash
uv run build-deck tech_adoption
```

Expected: `knowledge_base_tech_adoption.apkg` generated.

- [ ] **Step 4: Verify card count**

Expected: ~700-900 cards.

- [ ] **Step 5: Spot-check the .apkg**

```bash
cd /tmp && mkdir -p tech_check && cd tech_check && rm -f * && \
unzip /home/cmf/Dropbox/Apps/knowledge-base/knowledge_base_tech_adoption.apkg && \
sqlite3 collection.anki2 "SELECT COUNT(*) FROM notes" && echo "---" && \
sqlite3 collection.anki2 "SELECT flds FROM notes ORDER BY RANDOM() LIMIT 5"
```

Verify question format, answer rounding, and notes field look correct.

- [ ] **Step 6: Rebuild development deck to verify it still works**

```bash
uv run build-deck development
```

Expected: `knowledge_base.apkg` regenerated with same ~1,082 cards.

- [ ] **Step 7: Run all tests**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: generate Technology Adoption deck (~700-900 cards)"
```

---

## Task 5: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add the Technology Adoption deck to the "Current Decks" section. Update CLI usage to show the deck key argument. Update the project structure to show `data/development/` and `data/tech_adoption/`.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Technology Adoption deck to README"
```
