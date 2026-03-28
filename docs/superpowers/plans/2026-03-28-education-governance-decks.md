# Education & Governance Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new World Bank decks (education: 4 indicators, governance: 6 indicators) to the knowledge base, integrated into the existing fetch → import → review pipeline.

**Architecture:** Config-only changes to `config.py` — add two new `DECKS` entries following the exact pattern of existing WB decks (development, tech_adoption, etc.). Update `descriptive_stats.source_decks`. Create data directories. All pipeline code (fetch, import, review, build-deck) works unchanged.

**Tech Stack:** Python 3.12, polars, pytest, World Bank API (no auth)

---

### File Structure

- **Modify:** `src/knowledge_base/config.py` — add `education` and `governance` entries to `DECKS`, update `descriptive_stats.source_decks`
- **Modify:** `tests/test_config.py` — add tests for new decks
- **Create:** `data/education/.gitkeep` — empty directory marker
- **Create:** `data/governance/.gitkeep` — empty directory marker

---

### Task 1: Add Education Deck Config + Tests

**Files:**
- Modify: `tests/test_config.py`
- Modify: `src/knowledge_base/config.py`

- [ ] **Step 1: Write the failing test for education deck**

Add to `tests/test_config.py`:

```python
def test_education_deck_exists():
    assert "education" in DECKS
    deck = DECKS["education"]
    assert deck["name"] == "Knowledge Base::Education"
    assert deck["deck_id"] == 2026032806
    assert deck["data_dir"] == "data/education"
    assert len(deck["indicators"]) == 4
    eras = deck["era_ranges"]
    assert set(eras.keys()) == {"1990", "current"}
    assert eras["1990"] == (1988, 1992, 1990)
    assert eras["current"] == (2020, 2026, 2026)
    # All indicators are percentages — no scale_factor, no unit_prefix
    for ind in deck["indicators"]:
        assert ind.get("scale_factor", 1) == 1
        assert ind["unit_prefix"] == ""
        assert ind["category"] == "education"
        assert ind["has_regional_aggregates"] is True
    # Check specific indicator IDs
    ids = {i["id"] for i in deck["indicators"]}
    assert ids == {
        "adult_literacy",
        "secondary_enrollment",
        "tertiary_enrollment",
        "education_expenditure",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_education_deck_exists -v`
Expected: FAIL with `AssertionError` on `"education" in DECKS`

- [ ] **Step 3: Add education deck to config.py**

Insert the following into the `DECKS` dict in `src/knowledge_base/config.py`, after the `"finance"` entry and before `"urban_areas"`:

```python
    "education": {
        "name": "Knowledge Base::Education",
        "deck_id": 2026032806,
        "output": "knowledge_base_education.apkg",
        "data_dir": "data/education",
        "era_ranges": {
            "1990": (1988, 1992, 1990),
            "current": (2020, 2026, 2026),
        },
        "indicators": [
            {
                "id": "adult_literacy",
                "name": "Adult literacy rate",
                "category": "education",
                "unit_label": "% of people ages 15+",
                "wb_code": "SE.ADT.LITR.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "secondary_enrollment",
                "name": "Secondary school enrollment",
                "category": "education",
                "unit_label": "% gross",
                "wb_code": "SE.SEC.ENRR",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "tertiary_enrollment",
                "name": "Tertiary school enrollment",
                "category": "education",
                "unit_label": "% gross",
                "wb_code": "SE.TER.ENRR",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "education_expenditure",
                "name": "Government education expenditure",
                "category": "education",
                "unit_label": "% of GDP",
                "wb_code": "SE.XPD.TOTL.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
        ],
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_education_deck_exists -v`
Expected: PASS

- [ ] **Step 5: Run full config test suite**

Run: `uv run pytest tests/test_config.py -v`
Expected: All tests PASS (existing tests still pass)

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add education deck config (4 indicators, 1990/current eras)"
```

---

### Task 2: Add Governance Deck Config + Tests

**Files:**
- Modify: `tests/test_config.py`
- Modify: `src/knowledge_base/config.py`

- [ ] **Step 1: Write the failing test for governance deck**

Add to `tests/test_config.py`:

```python
def test_governance_deck_exists():
    assert "governance" in DECKS
    deck = DECKS["governance"]
    assert deck["name"] == "Knowledge Base::Governance"
    assert deck["deck_id"] == 2026032807
    assert deck["data_dir"] == "data/governance"
    assert len(deck["indicators"]) == 6
    eras = deck["era_ranges"]
    assert set(eras.keys()) == {"2000", "current"}
    assert eras["2000"] == (1998, 2002, 2000)
    assert eras["current"] == (2020, 2026, 2026)
    # All WGI indicators: same scale, 2 decimals, no regional aggregates
    for ind in deck["indicators"]:
        assert ind["decimals"] == 2
        assert ind["unit_prefix"] == ""
        assert ind["category"] == "governance"
        assert ind["has_regional_aggregates"] is False
        assert ind.get("scale_factor", 1) == 1
    # Check specific indicator IDs
    ids = {i["id"] for i in deck["indicators"]}
    assert ids == {
        "govt_effectiveness",
        "corruption_control",
        "rule_of_law",
        "regulatory_quality",
        "voice_accountability",
        "political_stability",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_governance_deck_exists -v`
Expected: FAIL with `AssertionError` on `"governance" in DECKS`

- [ ] **Step 3: Add governance deck to config.py**

Insert the following into the `DECKS` dict in `src/knowledge_base/config.py`, after the `"education"` entry and before `"urban_areas"`:

```python
    "governance": {
        "name": "Knowledge Base::Governance",
        "deck_id": 2026032807,
        "output": "knowledge_base_governance.apkg",
        "data_dir": "data/governance",
        "era_ranges": {
            "2000": (1998, 2002, 2000),
            "current": (2020, 2026, 2026),
        },
        "indicators": [
            {
                "id": "govt_effectiveness",
                "name": "Government effectiveness",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "GE.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "corruption_control",
                "name": "Control of corruption",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "CC.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "rule_of_law",
                "name": "Rule of law",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "RL.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "regulatory_quality",
                "name": "Regulatory quality",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "RQ.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "voice_accountability",
                "name": "Voice and accountability",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "VA.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "political_stability",
                "name": "Political stability",
                "category": "governance",
                "unit_label": "index (-2.5 to +2.5)",
                "wb_code": "PV.EST",
                "decimals": 2,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
        ],
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_governance_deck_exists -v`
Expected: PASS

- [ ] **Step 5: Run full config test suite**

Run: `uv run pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add governance deck config (6 WGI indicators, 2000/current eras)"
```

---

### Task 3: Update Descriptive Stats Source Decks + Test

**Files:**
- Modify: `src/knowledge_base/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_descriptive_stats_includes_new_decks():
    cfg = DECKS["descriptive_stats"]
    assert "education" in cfg["source_decks"]
    assert "governance" in cfg["source_decks"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_descriptive_stats_includes_new_decks -v`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Update source_decks in config.py**

In `src/knowledge_base/config.py`, change the `descriptive_stats` entry's `source_decks` from:

```python
        "source_decks": ["development", "tech_adoption", "conflict_security", "finance", "urban_areas"],
```

to:

```python
        "source_decks": ["development", "tech_adoption", "conflict_security", "finance", "education", "governance", "urban_areas"],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_descriptive_stats_includes_new_decks -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All 194+ tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add education + governance to descriptive_stats source_decks"
```

---

### Task 4: Create Data Directories + Fetch + Import

**Files:**
- Create: `data/education/.gitkeep`
- Create: `data/governance/.gitkeep`

- [ ] **Step 1: Create data directories with .gitkeep**

```bash
mkdir -p data/education data/governance
touch data/education/.gitkeep data/governance/.gitkeep
```

- [ ] **Step 2: Commit data directories**

```bash
git add data/education/.gitkeep data/governance/.gitkeep
git commit -m "chore: create data directories for education + governance decks"
```

- [ ] **Step 3: Fetch education data from World Bank API**

```bash
uv run fetch-data education
```

Expected: Writes CSV files to `data/education/` — one per indicator (4 files). Output shows fetched indicator names and row counts. Some entities/eras may have no data (especially literacy for some long-tail countries); this is expected.

- [ ] **Step 4: Verify education CSVs were created**

```bash
ls -la data/education/*.csv
```

Expected: 4 CSV files: `adult_literacy.csv`, `secondary_enrollment.csv`, `tertiary_enrollment.csv`, `education_expenditure.csv`

- [ ] **Step 5: Fetch governance data from World Bank API**

```bash
uv run fetch-data governance
```

Expected: Writes CSV files to `data/governance/` — one per indicator (6 files). WGI data should have good coverage for all 40 country entities. Regional entities will have no data (expected — `has_regional_aggregates: False`).

- [ ] **Step 6: Verify governance CSVs were created**

```bash
ls -la data/governance/*.csv
```

Expected: 6 CSV files: `govt_effectiveness.csv`, `corruption_control.csv`, `rule_of_law.csv`, `regulatory_quality.csv`, `voice_accountability.csv`, `political_stability.csv`

- [ ] **Step 7: Fetch updated descriptive stats**

```bash
uv run fetch-desc-stats
```

Expected: Regenerates `data/descriptive_stats/*.csv` now including education and governance indicators.

- [ ] **Step 8: Import education + governance into SRS database**

```bash
uv run srs-import education
uv run srs-import governance
uv run srs-import descriptive_stats
```

Expected: Each command reports cards imported/updated. Education should add ~280-320 cards. Governance should add ~400-440 cards. Descriptive stats should add ~30 new cards (10 indicators x 3 stats).

- [ ] **Step 9: Verify card counts via review stats**

```bash
uv run review --stats
```

Expected: Total cards should be ~5,000-5,200 (up from ~4,374). Education and governance decks should appear in the deck breakdown.
