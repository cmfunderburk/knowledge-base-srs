# Finance & Markets Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth Anki deck with 8 World Bank finance/macro indicators across the existing 47 entities and 3 eras.

**Architecture:** Config-only addition — new `DECKS["finance"]` entry in `config.py`, data directory, and documentation updates. No changes to pipeline code (`wb_api.py`, `fetch_data.py`, `build_deck.py`). Uses the existing `scale_factor` feature for two absolute-value indicators (reserves, remittances).

**Tech Stack:** Python 3.12+, polars, genanki, uv, pytest

**Spec:** `docs/superpowers/specs/2026-03-23-finance-deck-design.md`

---

## File Map

- **Modify:** `src/knowledge_base/config.py` — add `DECKS["finance"]` entry with 8 indicators
- **Modify:** `tests/test_config.py` — add `test_finance_deck_exists`
- **Create:** `data/finance/.gitkeep`
- **Modify:** `CLAUDE.md` — add `finance` to available deck keys
- **Modify:** `README.md` — add Finance & Markets deck section

---

### Task 1: Add `finance` deck to config

**Files:**
- Modify: `src/knowledge_base/config.py` (add DECKS entry after conflict_security)
- Modify: `tests/test_config.py` (add deck existence test)

- [ ] **Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_finance_deck_exists():
    assert "finance" in DECKS
    deck = DECKS["finance"]
    assert len(deck["indicators"]) == 8
    eras = deck["era_ranges"]
    assert "1960" in eras
    assert "1990" in eras
    assert "current" in eras
    # Verify scale_factor on absolute-value indicators
    indicators_by_id = {i["id"]: i for i in deck["indicators"]}
    assert indicators_by_id["reserves"]["scale_factor"] == 1_000_000_000
    assert indicators_by_id["remittances"]["scale_factor"] == 1_000_000_000
    # Verify categories
    categories = {i["category"] for i in deck["indicators"]}
    assert categories == {"macro", "financial_system"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_finance_deck_exists -v`
Expected: FAIL with KeyError "finance"

- [ ] **Step 3: Add DECKS["finance"] entry**

In `src/knowledge_base/config.py`, after the `"conflict_security"` entry in `DECKS`, add:

```python
    "finance": {
        "name": "Knowledge Base::Finance & Markets",
        "deck_id": 2026032303,
        "output": "knowledge_base_finance.apkg",
        "data_dir": "data/finance",
        "era_ranges": {
            "1960": (1955, 1965, 1960),
            "1990": (1988, 1992, 1990),
            "current": (2020, 2026, 2026),
        },
        "indicators": [
            {
                "id": "inflation",
                "name": "Inflation (CPI)",
                "category": "macro",
                "unit_label": "annual %",
                "wb_code": "FP.CPI.TOTL.ZG",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "current_account",
                "name": "Current account balance",
                "category": "macro",
                "unit_label": "% of GDP",
                "wb_code": "BN.CAB.XOKA.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "reserves",
                "name": "Total reserves including gold",
                "category": "macro",
                "unit_label": "billions of current US$",
                "wb_code": "FI.RES.TOTL.CD",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1_000_000_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "real_interest_rate",
                "name": "Real interest rate",
                "category": "macro",
                "unit_label": "%",
                "wb_code": "FR.INR.RINR",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": False,
            },
            {
                "id": "market_cap",
                "name": "Market capitalization",
                "category": "financial_system",
                "unit_label": "% of GDP",
                "wb_code": "CM.MKT.LCAP.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "stocks_traded",
                "name": "Stocks traded",
                "category": "financial_system",
                "unit_label": "% of GDP",
                "wb_code": "CM.MKT.TRAD.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "domestic_credit",
                "name": "Domestic credit to private sector",
                "category": "financial_system",
                "unit_label": "% of GDP",
                "wb_code": "FS.AST.PRVT.GD.ZS",
                "decimals": 1,
                "unit_prefix": "",
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
            {
                "id": "remittances",
                "name": "Personal remittances received",
                "category": "financial_system",
                "unit_label": "billions of current US$",
                "wb_code": "BX.TRF.PWKR.CD.DT",
                "decimals": 1,
                "unit_prefix": "",
                "scale_factor": 1_000_000_000,
                "time_invariant": False,
                "current_only": False,
                "has_regional_aggregates": True,
            },
        ],
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all 29 tests PASS (28 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/config.py tests/test_config.py
git commit -m "feat: add finance deck with 8 indicators"
```

---

### Task 2: Data directory and docs

**Files:**
- Create: `data/finance/.gitkeep`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Create data directory**

```bash
mkdir -p data/finance
touch data/finance/.gitkeep
```

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, change:

```
Available deck keys: `development`, `tech_adoption`, `conflict_security`
```

To:

```
Available deck keys: `development`, `tech_adoption`, `conflict_security`, `finance`
```

- [ ] **Step 3: Update README.md**

Add a new deck section after the Conflict & Security section. Follow the same format:

```markdown
### Finance & Markets

**~550–700 cards** covering 8 indicators across 47 entities and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Macro | Inflation (CPI), current account balance, total reserves including gold, real interest rate |
| Financial System | Market capitalization, stocks traded, domestic credit to private sector, personal remittances received |

**Data source:** World Bank WDI (API).

**Time periods:** Bretton Woods era baseline (~1960), post-Cold War financial globalization (~1990), and current — tracking the evolution of global financial systems.
```

Also update the Setup section to include the new deck commands:

```bash
uv run fetch-data finance           # download data → data/finance/*.csv
uv run build-deck finance           # generate knowledge_base_finance.apkg
```

Update the Project Structure `data/` section:

```
    finance/           # Curated CSVs for finance deck (gitignored)
```

Update the Tag Schema section to include `category::macro`, `category::financial_system`.

Update the test count in the Setup section if shown (currently says 25 tests — should say 29).

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: all 29 tests PASS

- [ ] **Step 5: Commit**

```bash
git add data/finance/.gitkeep CLAUDE.md README.md
git commit -m "docs: add finance deck to docs and create data directory"
```

---

### Task 3: Fetch data and build deck

This is a manual verification step. No tests — just run the pipeline and confirm output.

- [ ] **Step 1: Fetch finance data**

```bash
uv run fetch-data finance
```

Expected: 8 CSVs written to `data/finance/` (one per indicator). Some indicators may have fewer rows than others (market_cap and stocks_traded will lack 1960 era data for most countries).

- [ ] **Step 2: Build finance deck**

```bash
uv run build-deck finance
```

Expected: `knowledge_base_finance.apkg` created in repo root. Card count should be ~550–700.

- [ ] **Step 3: Spot-check a few cards**

Open the `.apkg` file with SQLite to verify:
- An inflation card shows a reasonable value (e.g., USA ~3% current, India ~5%)
- A reserves card shows a scaled answer in billions (e.g., China ~3,400)
- Reference averages in Notes are present for indicators with regional aggregates
- Tags include `category::macro` and `category::financial_system`

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -v
```

Expected: all 29 tests PASS
