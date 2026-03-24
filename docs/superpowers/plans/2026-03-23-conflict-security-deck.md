# Conflict & Security Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `scale_factor` pipeline feature and a third Anki deck (Conflict & Security) with 7 World Bank indicators.

**Architecture:** Two independent concerns: (1) a cross-cutting `scale_factor` field that divides raw API values before generating card answers and reference averages, with retroactive application to the development deck's population indicators; (2) a new `DECKS["conflict_security"]` config entry using the existing pipeline unchanged. All data comes from the World Bank WDI API via the existing `wb_api.py` client.

**Tech Stack:** Python 3.12+, polars, genanki, uv, pytest

**Spec:** `docs/superpowers/specs/2026-03-23-conflict-security-deck-design.md`

---

## File Map

- **Modify:** `src/knowledge_base/config.py` — add `scale_factor` to `population` and `city_population` indicators in development deck, add `DECKS["conflict_security"]` entry with 7 indicators
- **Modify:** `src/knowledge_base/build_deck.py:307-313` — update `format_answer()` to divide by `scale_factor`; update `_run()` call sites (~lines 498-527, 543) to scale reference averages and city `country_population`
- **Modify:** `tests/test_build_deck.py` — add `test_format_answer_with_scale_factor`, `test_format_answer_default_scale_factor`
- **Modify:** `tests/test_config.py` — add `test_conflict_security_deck_exists`
- **Create:** `data/conflict_security/.gitkeep`
- **Modify:** `CLAUDE.md` — add `conflict_security` to available deck keys
- **Modify:** `README.md` — add Conflict & Security deck section

---

### Task 1: Add `scale_factor` support to `format_answer`

**Files:**
- Modify: `tests/test_build_deck.py`
- Modify: `src/knowledge_base/build_deck.py:307-313`

- [ ] **Step 1: Write failing tests for format_answer with scale_factor**

Add to `tests/test_build_deck.py`:

```python
from knowledge_base.build_deck import (
    generate_question,
    generate_notes,
    generate_notes_city,
    generate_notes_land_area,
    compute_reference_averages,
    build_tags,
    format_answer,
)


def test_format_answer_with_scale_factor():
    indicator = {"decimals": 1, "scale_factor": 1_000_000_000}
    result = format_answer(2_345_000_000, indicator)
    assert result == "2.3"


def test_format_answer_default_scale_factor():
    indicator = {"decimals": 0}
    result = format_answer(8379, indicator)
    assert result == "8379"
```

Note: also add `format_answer` to the import at the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_deck.py::test_format_answer_with_scale_factor tests/test_build_deck.py::test_format_answer_default_scale_factor -v`
Expected: `test_format_answer_with_scale_factor` FAIL (no scale_factor handling), `test_format_answer_default_scale_factor` PASS

- [ ] **Step 3: Update format_answer to support scale_factor**

In `src/knowledge_base/build_deck.py`, replace `format_answer`:

```python
def format_answer(value: float, indicator: dict) -> str:
    """Round and format a numerical answer for the card."""
    scale_factor = indicator.get("scale_factor", 1)
    decimals = indicator.get("decimals", 1)
    scaled = value / scale_factor
    rounded = round(scaled, decimals)
    if decimals == 0:
        return str(int(rounded))
    return f"{rounded:.{decimals}f}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_deck.py -v`
Expected: all 10 tests PASS (8 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add tests/test_build_deck.py src/knowledge_base/build_deck.py
git commit -m "feat: add scale_factor support to format_answer"
```

---

### Task 2: Apply `scale_factor` to reference averages and city notes in `_run`

**Files:**
- Modify: `src/knowledge_base/build_deck.py:496-527, 543`

The `_run` function in `build_deck.py` has three code paths for generating the Notes field. Two need scaling applied at the call site.

- [ ] **Step 1: Scale reference averages in the generic notes path**

In `src/knowledge_base/build_deck.py`, in the `_run` function, find the generic notes generation block (the `else` clause around line 515). Change:

```python
            else:
                world_avg, region_avgs = ref_by_era.get(
                    era, (None, {})
                )
                region_name = entity_cfg.get("region", "")
                regional_avg = region_avgs.get(region_name)
                notes = generate_notes(
                    source=source,
                    world_avg=world_avg,
                    regional_avg=regional_avg,
                    unit_prefix=unit_prefix,
                    decimals=indicator.get("decimals", 1),
                )
```

To:

```python
            else:
                world_avg, region_avgs = ref_by_era.get(
                    era, (None, {})
                )
                region_name = entity_cfg.get("region", "")
                regional_avg = region_avgs.get(region_name)
                scale_factor = indicator.get("scale_factor", 1)
                scaled_world = world_avg / scale_factor if world_avg is not None else None
                scaled_regional = regional_avg / scale_factor if regional_avg is not None else None
                notes = generate_notes(
                    source=source,
                    world_avg=scaled_world,
                    regional_avg=scaled_regional,
                    unit_prefix=unit_prefix,
                    decimals=indicator.get("decimals", 1),
                )
```

- [ ] **Step 2: Scale country_population in the city notes path**

In the same `_run` function, find the city notes block (around line 497). Change:

```python
            if is_city:
                country_pop = row.get("country_population", 0)
                notes = generate_notes_city(
                    source=source,
                    country_population=country_pop,
                )
```

To:

```python
            if is_city:
                country_pop = row.get("country_population", 0)
                scale_factor = indicator.get("scale_factor", 1)
                notes = generate_notes_city(
                    source=source,
                    country_population=country_pop / scale_factor,
                )
```

- [ ] **Step 3: Run all tests to verify nothing breaks**

Run: `uv run pytest -v`
Expected: all 27 tests PASS (25 existing + 2 from Task 1; no behavioral change yet since no indicators have scale_factor != 1)

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/build_deck.py
git commit -m "feat: apply scale_factor to reference averages and city notes in _run"
```

---

### Task 3: Retroactive `scale_factor` changes to development deck config

**Files:**
- Modify: `src/knowledge_base/config.py:492-527` (population and city_population indicators)

- [ ] **Step 1: Update `population` indicator**

In `src/knowledge_base/config.py`, in `DECKS["development"]["indicators"]`, find the `population` entry (id `"population"`) and add `"scale_factor": 1_000_000` and change `"unit_label"` from `"people"` to `"millions"`:

```python
            {
                "id": "population",
                "name": "Population",
                "category": "geography",
                "unit_label": "millions",
                "wb_code": "SP.POP.TOTL",
                "decimals": 0,
                "unit_prefix": "",
                "scale_factor": 1_000_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
```

- [ ] **Step 2: Update `city_population` indicator**

Find the `city_population` entry and add `"scale_factor": 1_000_000`, change `"unit_label"` from `"people (metro area)"` to `"millions (metro area)"`, and change `"decimals"` from `0` to `1`:

```python
            {
                "id": "city_population",
                "name": "Major city populations",
                "category": "geography",
                "unit_label": "millions (metro area)",
                "wb_code": None,
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1_000_000,
                "time_invariant": False,
                "current_only": True,
                "has_regional_aggregates": False,
            },
```

- [ ] **Step 3: Run all tests to verify nothing breaks**

Run: `uv run pytest -v`
Expected: all 27 tests PASS. The config tests check for field presence (not values), and the build tests don't exercise scale_factor through _run.

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/config.py
git commit -m "feat: add scale_factor to population and city_population indicators"
```

---

### Task 4: Add `conflict_security` deck to config

**Files:**
- Modify: `src/knowledge_base/config.py` (add DECKS entry after tech_adoption)
- Modify: `tests/test_config.py` (add deck existence test)

- [ ] **Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_conflict_security_deck_exists():
    assert "conflict_security" in DECKS
    deck = DECKS["conflict_security"]
    assert len(deck["indicators"]) == 7
    eras = deck["era_ranges"]
    assert "1960" in eras
    assert "1990" in eras
    assert "current" in eras
    # Verify scale_factor on indicators that need it
    indicators_by_id = {i["id"]: i for i in deck["indicators"]}
    assert indicators_by_id["mil_expenditure_usd"]["scale_factor"] == 1_000_000_000
    assert indicators_by_id["armed_forces"]["scale_factor"] == 1_000
    assert indicators_by_id["arms_imports"]["scale_factor"] == 1_000_000
    assert indicators_by_id["refugees_origin"]["scale_factor"] == 1_000
    assert indicators_by_id["refugees_asylum"]["scale_factor"] == 1_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_conflict_security_deck_exists -v`
Expected: FAIL with KeyError "conflict_security"

- [ ] **Step 3: Add DECKS["conflict_security"] entry**

In `src/knowledge_base/config.py`, after the `"tech_adoption"` entry in `DECKS`, add:

```python
    "conflict_security": {
        "name": "Knowledge Base::Conflict & Security",
        "deck_id": 2026032302,
        "output": "knowledge_base_conflict_security.apkg",
        "data_dir": "data/conflict_security",
        "era_ranges": {
            "1960": (1955, 1965, 1960),
            "1990": (1988, 1992, 1990),
            "current": (2020, 2026, 2026),
        },
        "indicators": [
            {
                "id": "mil_expenditure_gdp",
                "name": "Military expenditure",
                "category": "military",
                "unit_label": "% of GDP",
                "wb_code": "MS.MIL.XPND.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "mil_expenditure_usd",
                "name": "Military expenditure",
                "category": "military",
                "unit_label": "billions of current US$",
                "wb_code": "MS.MIL.XPND.CD",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1_000_000_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "armed_forces",
                "name": "Armed forces personnel",
                "category": "military",
                "unit_label": "thousands",
                "wb_code": "MS.MIL.TOTL.P1",
                "decimals": 0,
                "unit_prefix": "",
                "scale_factor": 1_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "arms_imports",
                "name": "Arms imports",
                "category": "military",
                "unit_label": "millions (constant 1990 US$)",
                "wb_code": "MS.MIL.MPRT.KD",
                "decimals": 0,
                "unit_prefix": "",
                "scale_factor": 1_000_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "homicides",
                "name": "Intentional homicides",
                "category": "security",
                "unit_label": "per 100,000 people",
                "wb_code": "VC.IHR.PSRC.P5",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "refugees_origin",
                "name": "Refugees by country of origin",
                "category": "security",
                "unit_label": "thousands",
                "wb_code": "SM.POP.RHCR.EO",
                "decimals": 0,
                "unit_prefix": "",
                "scale_factor": 1_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "refugees_asylum",
                "name": "Refugees by country of asylum",
                "category": "security",
                "unit_label": "thousands",
                "wb_code": "SM.POP.RHCR.EA",
                "decimals": 0,
                "unit_prefix": "",
                "scale_factor": 1_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
        ],
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all 28 tests PASS (25 existing + 2 from Task 1 + 1 new)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add conflict_security deck with 7 indicators"
```

---

### Task 5: Data directory, docs, and integration

**Files:**
- Create: `data/conflict_security/.gitkeep`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Create data directory**

```bash
mkdir -p data/conflict_security
touch data/conflict_security/.gitkeep
```

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, change:

```
Available deck keys: `development`, `tech_adoption`
```

To:

```
Available deck keys: `development`, `tech_adoption`, `conflict_security`
```

- [ ] **Step 3: Update README.md**

Add a new deck section after the Technology Adoption section. Follow the same format as existing deck sections:

```markdown
### Conflict & Security

**~450–600 cards** covering 7 indicators across 47 entities and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Military | Military expenditure (% of GDP), military expenditure (USD), armed forces personnel, arms imports |
| Security | Intentional homicides, refugees by country of origin, refugees by country of asylum |

**Data source:** World Bank WDI (API).

**Time periods:** Cold War baseline (~1960), end of Cold War (~1990), and current — bracketing the Cold War, post-Cold War drawdown, and present-day security landscape.
```

Also update the Setup section to include the new deck commands:

```bash
uv run fetch-data conflict_security  # download data → data/conflict_security/*.csv
uv run build-deck conflict_security  # generate knowledge_base_conflict_security.apkg
```

And update the Project Structure `data/` section:

```
    conflict_security/ # Curated CSVs for conflict & security deck (gitignored)
```

And update the Tag Schema section to include `category::military`, `category::security`.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: all 28 tests PASS

- [ ] **Step 5: Commit**

```bash
git add data/conflict_security/.gitkeep CLAUDE.md README.md
git commit -m "docs: add conflict_security deck to docs and create data directory"
```

---

### Task 6: Fetch data and build decks

This is a manual verification step. No tests — just run the pipeline and confirm output.

- [ ] **Step 1: Fetch conflict_security data**

```bash
uv run fetch-data conflict_security
```

Expected: 7 CSVs written to `data/conflict_security/` (one per indicator). Some indicators may have fewer rows than others (armed forces and homicides will lack 1960 era data).

- [ ] **Step 2: Build conflict_security deck**

```bash
uv run build-deck conflict_security
```

Expected: `knowledge_base_conflict_security.apkg` created in repo root. Card count should be ~450–600.

- [ ] **Step 3: Rebuild development deck with scaled population**

```bash
uv run build-deck development
```

Expected: `knowledge_base.apkg` regenerated. Population and city population cards now use scaled values (millions). Total card count should remain ~1,082 (same cards, different answer formatting).

- [ ] **Step 4: Spot-check a few cards**

Open the `.apkg` files in a text editor or SQLite browser to verify:
- A conflict_security card shows a scaled answer (e.g., USA military expenditure ~886 billions, not 886000000000)
- A development deck population card shows ~1426 (millions) for China, not 1425893000
- Reference averages in Notes fields are also scaled appropriately

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all 28 tests PASS

- [ ] **Step 6: Commit any generated files if needed**

The `.apkg` files and `data/**/*.csv` files are gitignored, so no commit needed here. But if any file was missed in previous commits:

```bash
git status
# Stage and commit anything that should be tracked
```
