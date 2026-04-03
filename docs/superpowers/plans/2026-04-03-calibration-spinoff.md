# Calibration System Spin-Off Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the calibration review system into a standalone project at `/home/cmf/Dropbox/Apps/calibration` and clean up `knowledge_base` to focus on initial-encoding massed/ordered practice.

**Architecture:** Copy calibration source, SRS, test, and fixture files to a new project preserving the `src/knowledge_base/` package layout (zero import rewrites). Then delete all calibration code from the original repo, remove unused deps/entry points, and update `CLAUDE.md`.

**Tech Stack:** Python 3.12, uv, hatchling, genanki, httpx, polars, textual, pytest

---

### Task 1: Scaffold the calibration project

**Files:**
- Create: `/home/cmf/Dropbox/Apps/calibration/pyproject.toml`
- Create: `/home/cmf/Dropbox/Apps/calibration/.gitignore`
- Create: `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/__init__.py`
- Create: `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/srs/__init__.py`

- [ ] **Step 1: Create project directories**

```bash
mkdir -p /home/cmf/Dropbox/Apps/calibration/src/knowledge_base/srs
mkdir -p /home/cmf/Dropbox/Apps/calibration/tests/fixtures/sample_srs_import
mkdir -p /home/cmf/Dropbox/Apps/calibration/data/{development,tech_adoption,conflict_security,finance,education,governance,urban_areas,descriptive_stats}
mkdir -p /home/cmf/Dropbox/Apps/calibration/resources
```

- [ ] **Step 2: Create `pyproject.toml`**

Write to `/home/cmf/Dropbox/Apps/calibration/pyproject.toml`:

```toml
[project]
name = "calibration"
version = "0.1.0"
description = "Calibration training system for confidence-interval estimation on real-world indicators"
requires-python = ">=3.12"
dependencies = [
    "genanki>=0.13",
    "httpx>=0.27",
    "polars>=1.0",
    "textual>=3.0",
]

[project.scripts]
fetch-data = "knowledge_base.fetch_data:main"
fetch-urban-data = "knowledge_base.fetch_urban_data:main"
fetch-desc-stats = "knowledge_base.fetch_desc_stats:main"
build-deck = "knowledge_base.build_deck:main"
review = "knowledge_base.srs.tui:main"
srs-import = "knowledge_base.srs.importer:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create `.gitignore`**

Write to `/home/cmf/Dropbox/Apps/calibration/.gitignore`:

```
data/**/*.csv
data/**/*.db
data/**/*.json
*.apkg
*.env
resources/
__pycache__/
.venv/
.worktrees/
```

- [ ] **Step 4: Create `__init__.py` files**

Write to `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/__init__.py`:

```python
def hello() -> str:
    return "Hello from calibration!"
```

Write `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/srs/__init__.py` as an empty file.

- [ ] **Step 5: Create `.gitkeep` files**

```bash
for d in development tech_adoption conflict_security finance education governance urban_areas descriptive_stats; do
    touch /home/cmf/Dropbox/Apps/calibration/data/$d/.gitkeep
done
```

- [ ] **Step 6: Initialize git and commit scaffold**

```bash
cd /home/cmf/Dropbox/Apps/calibration
git init
git add .
git commit -m "chore: scaffold calibration project structure"
```

---

### Task 2: Copy source modules

**Files:**
- Copy: `src/knowledge_base/config.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/config.py`
- Copy: `src/knowledge_base/wb_api.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/wb_api.py`
- Copy: `src/knowledge_base/ghsl.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/ghsl.py`
- Copy: `src/knowledge_base/card_gen.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/card_gen.py`
- Copy: `src/knowledge_base/desc_stats.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/desc_stats.py`
- Copy: `src/knowledge_base/fetch_data.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/fetch_data.py`
- Copy: `src/knowledge_base/fetch_urban_data.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/fetch_urban_data.py`
- Copy: `src/knowledge_base/fetch_desc_stats.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/fetch_desc_stats.py`
- Copy: `src/knowledge_base/build_deck.py` → `/home/cmf/Dropbox/Apps/calibration/src/knowledge_base/build_deck.py`

- [ ] **Step 1: Copy top-level source modules**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
for f in config.py wb_api.py ghsl.py card_gen.py desc_stats.py fetch_data.py fetch_urban_data.py fetch_desc_stats.py build_deck.py; do
    cp src/knowledge_base/$f /home/cmf/Dropbox/Apps/calibration/src/knowledge_base/$f
done
```

- [ ] **Step 2: Copy SRS modules**

```bash
for f in scoring.py scheduler.py db.py importer.py stats.py tui.py; do
    cp src/knowledge_base/srs/$f /home/cmf/Dropbox/Apps/calibration/src/knowledge_base/srs/$f
done
```

- [ ] **Step 3: Commit source modules**

```bash
cd /home/cmf/Dropbox/Apps/calibration
git add src/
git commit -m "feat: copy calibration source modules from knowledge_base"
```

---

### Task 3: Copy tests and fixtures

**Files:**
- Copy: 16 test files from `tests/` → `/home/cmf/Dropbox/Apps/calibration/tests/`
- Copy: `tests/fixtures/` → `/home/cmf/Dropbox/Apps/calibration/tests/fixtures/`

- [ ] **Step 1: Copy test files**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
for f in test_wb_api.py test_fetch_data.py test_ghsl.py test_fetch_urban_data.py test_desc_stats.py test_fetch_desc_stats.py test_build_deck.py test_card_gen.py test_config.py test_scoring.py test_scheduler.py test_srs_db.py test_importer.py test_stats.py test_integration.py test_srs_integration.py; do
    cp tests/$f /home/cmf/Dropbox/Apps/calibration/tests/$f
done
```

- [ ] **Step 2: Copy fixtures**

```bash
cp /home/cmf/Dropbox/Apps/knowledge-base/tests/fixtures/sample_gdp.csv /home/cmf/Dropbox/Apps/calibration/tests/fixtures/
cp /home/cmf/Dropbox/Apps/knowledge-base/tests/fixtures/sample_urban.gpkg /home/cmf/Dropbox/Apps/calibration/tests/fixtures/
cp /home/cmf/Dropbox/Apps/knowledge-base/tests/fixtures/create_urban_fixture.py /home/cmf/Dropbox/Apps/calibration/tests/fixtures/
cp /home/cmf/Dropbox/Apps/knowledge-base/tests/fixtures/sample_srs_import/gdp_pc_ppp.csv /home/cmf/Dropbox/Apps/calibration/tests/fixtures/sample_srs_import/
cp /home/cmf/Dropbox/Apps/knowledge-base/tests/fixtures/sample_srs_import/desc_stats_gdp_pc_ppp.csv /home/cmf/Dropbox/Apps/calibration/tests/fixtures/sample_srs_import/
```

- [ ] **Step 3: Commit tests and fixtures**

```bash
cd /home/cmf/Dropbox/Apps/calibration
git add tests/
git commit -m "feat: copy calibration tests and fixtures from knowledge_base"
```

---

### Task 4: Verify calibration project builds and passes tests

**Files:**
- None (verification only)

- [ ] **Step 1: Install dependencies**

```bash
cd /home/cmf/Dropbox/Apps/calibration
uv sync
```

- [ ] **Step 2: Run all tests**

```bash
cd /home/cmf/Dropbox/Apps/calibration
uv run pytest -v
```

Expected: All 16 test files pass. If any failures, fix import issues before proceeding.

- [ ] **Step 3: Verify entry points work**

```bash
cd /home/cmf/Dropbox/Apps/calibration
uv run review --help 2>&1 | head -5
```

Expected: Help text or no import errors. (The TUI won't launch without `--help` or a deck argument, but the import chain should resolve.)

---

### Task 5: Write calibration `CLAUDE.md`

**Files:**
- Create: `/home/cmf/Dropbox/Apps/calibration/CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

Write to `/home/cmf/Dropbox/Apps/calibration/CLAUDE.md`. Content should be extracted from the current `knowledge_base` `CLAUDE.md`, keeping only:

- **Project Overview**: Rewrite as "TUI-based calibration training system for confidence-interval estimation on real-world indicators."
- **Quick Reference**: Only `fetch-data`, `fetch-urban-data`, `fetch-desc-stats`, `build-deck`, `review`, `srs-import` commands. Include `uv sync` and `uv run pytest`.
- **Architecture**: Only the calibration pipeline diagram (`config.py → fetch-data → CSVs → srs-import → srs.db → review TUI → build-deck → .apkg`).
- **Key files**: `scoring.py`, `scheduler.py`, `db.py`, `importer.py`, `stats.py`, `tui.py`, `config.py`, `wb_api.py`, `ghsl.py`, `card_gen.py`, `build_deck.py`, and the fetch scripts.
- **Adding a New Calibration Deck**: The full 6-step process from the current CLAUDE.md.
- **Calibration scoring**: Answer-normalized log-likelihood section, point prediction scoring, display units.
- **Calibration scheduling**: Power-law forgetting curve, continuous score → stability, desired retention, initial stability, 23 params.
- **Anki export**: Model ID, card templates, GUID stability.
- **Data sources**: World Bank API quirks.
- **Code Style**: Same conventions (Python 3.12+, uv, polars, textual, pytest).
- **Data**: CSVs gitignored, srs.db gitignored, resources gitignored.

Omit all generation review, masking, catalog, markdown import, massed/ordered practice, and FSRS v6 content.

- [ ] **Step 2: Commit**

```bash
cd /home/cmf/Dropbox/Apps/calibration
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md for calibration project"
```

---

### Task 6: Remove calibration source modules from `knowledge_base`

**Files:**
- Delete: `src/knowledge_base/config.py`
- Delete: `src/knowledge_base/wb_api.py`
- Delete: `src/knowledge_base/ghsl.py`
- Delete: `src/knowledge_base/card_gen.py`
- Delete: `src/knowledge_base/desc_stats.py`
- Delete: `src/knowledge_base/fetch_data.py`
- Delete: `src/knowledge_base/fetch_urban_data.py`
- Delete: `src/knowledge_base/fetch_desc_stats.py`
- Delete: `src/knowledge_base/build_deck.py`
- Delete: `src/knowledge_base/srs/scoring.py`
- Delete: `src/knowledge_base/srs/scheduler.py`
- Delete: `src/knowledge_base/srs/db.py`
- Delete: `src/knowledge_base/srs/importer.py`
- Delete: `src/knowledge_base/srs/stats.py`
- Delete: `src/knowledge_base/srs/tui.py`

- [ ] **Step 1: Delete top-level calibration modules**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
rm src/knowledge_base/config.py
rm src/knowledge_base/wb_api.py
rm src/knowledge_base/ghsl.py
rm src/knowledge_base/card_gen.py
rm src/knowledge_base/desc_stats.py
rm src/knowledge_base/fetch_data.py
rm src/knowledge_base/fetch_urban_data.py
rm src/knowledge_base/fetch_desc_stats.py
rm src/knowledge_base/build_deck.py
```

- [ ] **Step 2: Delete SRS calibration modules**

```bash
rm src/knowledge_base/srs/scoring.py
rm src/knowledge_base/srs/scheduler.py
rm src/knowledge_base/srs/db.py
rm src/knowledge_base/srs/importer.py
rm src/knowledge_base/srs/stats.py
rm src/knowledge_base/srs/tui.py
```

- [ ] **Step 3: Commit removals**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
git add -u src/
git commit -m "refactor: remove calibration source modules (moved to calibration project)"
```

---

### Task 7: Remove calibration tests, fixtures, and data scaffolding

**Files:**
- Delete: 16 test files
- Delete: `tests/fixtures/` directory
- Delete: 8 `data/*/.gitkeep` directories

- [ ] **Step 1: Delete calibration test files**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
rm tests/test_wb_api.py
rm tests/test_fetch_data.py
rm tests/test_ghsl.py
rm tests/test_fetch_urban_data.py
rm tests/test_desc_stats.py
rm tests/test_fetch_desc_stats.py
rm tests/test_build_deck.py
rm tests/test_card_gen.py
rm tests/test_config.py
rm tests/test_scoring.py
rm tests/test_scheduler.py
rm tests/test_srs_db.py
rm tests/test_importer.py
rm tests/test_stats.py
rm tests/test_integration.py
rm tests/test_srs_integration.py
```

- [ ] **Step 2: Delete fixtures directory**

```bash
rm -rf tests/fixtures/
```

- [ ] **Step 3: Delete calibration data directories**

```bash
rm -rf data/development data/tech_adoption data/conflict_security data/finance data/education data/governance data/urban_areas data/descriptive_stats
```

- [ ] **Step 4: Remove the coexistence test from `test_generation_db.py`**

In `tests/test_generation_db.py`, delete the entire `test_coexists_with_srs_db_in_same_file` method. Search for `def test_coexists_with_srs_db_in_same_file` — it's the only method that imports from `knowledge_base.srs.db`, which no longer exists. Remove the method and its body (roughly 24 lines including the docstring).

- [ ] **Step 5: Commit**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
git add -u tests/ data/
git commit -m "refactor: remove calibration tests, fixtures, and data directories"
```

---

### Task 8: Update `pyproject.toml` — remove calibration entry points and unused deps

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove calibration entry points and unused dependencies**

Edit `pyproject.toml` to become:

```toml
[project]
name = "knowledge-base"
version = "0.1.0"
description = "Initial-encoding aid for structured study material via progressive masking and massed practice"
requires-python = ">=3.12"
dependencies = [
    "genanki>=0.13",
    "textual>=3.0",
]

[project.scripts]
review-gen = "knowledge_base.srs.generation_tui:main"
gen-import = "knowledge_base.srs.generation_import:main"
gen-import-md = "knowledge_base.srs.md_importer:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Changes: removed `httpx`, `polars` from dependencies. Removed 6 calibration entry points. Updated project description.

- [ ] **Step 2: Re-sync dependencies**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
uv sync
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "refactor: remove calibration entry points and unused dependencies"
```

---

### Task 9: Verify `knowledge_base` tests pass after cleanup

**Files:**
- None (verification only)

- [ ] **Step 1: Run remaining tests**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
uv run pytest -v
```

Expected: All remaining generation tests pass (~10 test files: `test_fsrs.py`, `test_masking.py`, `test_text_scoring.py`, `test_catalog.py`, `test_generation_db.py`, `test_generation_import.py`, `test_generation_integration.py`, `test_md_importer.py`, `test_ordered_practice.py`, `test_paste_drill.py`).

- [ ] **Step 2: Verify entry points**

```bash
uv run review-gen --help 2>&1 | head -5
```

Expected: No import errors.

- [ ] **Step 3: Fix any failures**

If any tests fail due to stale imports referencing removed calibration modules, fix them. The known case is the coexistence test removed in Task 7 Step 4. If others surface, they should be import-path issues only — delete the offending imports or tests.

---

### Task 10: Update `knowledge_base` `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Rewrite `CLAUDE.md`**

Update the existing `CLAUDE.md` with these changes:

**Project Overview**: Change to "TUI-based initial-encoding aid for drilling structured study material through progressive masking and massed/ordered practice. Import markdown study notes or paste raw text, then drill through masking levels that build recall. A catalog TUI lets you browse and select material across multiple sources and topics. Once material reaches 3+ successful passes, export to Anki for long-term spaced retrieval via FSRS."

**Quick Reference**: Remove all calibration commands (`fetch-data`, `fetch-urban-data`, `fetch-desc-stats`, `srs-import`, `review`, `build-deck`). Remove the calibration deck keys list. Keep all `review-gen` and `gen-import` commands.

**Architecture**: Remove the calibration pipeline diagram. Keep only the generation review pipeline:

```
markdown files ──→ gen-import-md ──→ data/srs.db ──→ review-gen TUI
cfa_level1_los.json ──→ gen-import ─┘                    │
                                                   catalog TUI (browse/select)
```

Remove all subsections under "### Calibration review" and "### Shared / data pipeline". Keep "### Generation review".

**Key Constraints**: Remove the entire "### Calibration scoring", "### Calibration scheduling", "### Anki export", and "### Data sources" sections. Keep "### Generation cards (multi-source)".

**Code Style**: Remove `polars` reference (no longer a dependency). Keep everything else.

**Data**: Remove references to CSVs generated by `fetch-data` and `resources/`. Keep `data/srs.db` and `data/cfa_level1_los.json` references. Remove "Adding a New Calibration Deck" section entirely.

- [ ] **Step 2: Commit**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md focused on initial-encoding massed practice"
```

---

### Task 11: Final verification of both projects

**Files:**
- None (verification only)

- [ ] **Step 1: Run calibration tests**

```bash
cd /home/cmf/Dropbox/Apps/calibration
uv run pytest -v
```

Expected: All calibration tests pass.

- [ ] **Step 2: Run knowledge_base tests**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
uv run pytest -v
```

Expected: All generation tests pass.

- [ ] **Step 3: Verify no cross-references remain**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
grep -r "from knowledge_base.srs.scoring\|from knowledge_base.srs.scheduler\|from knowledge_base.srs.db\b\|from knowledge_base.srs.importer\|from knowledge_base.srs.stats\|from knowledge_base.srs.tui\b\|from knowledge_base.config\|from knowledge_base.wb_api\|from knowledge_base.ghsl\|from knowledge_base.card_gen\|from knowledge_base.desc_stats\|from knowledge_base.fetch_data\|from knowledge_base.fetch_urban\|from knowledge_base.build_deck" src/ tests/ || echo "No stale calibration imports found"
```

Expected: "No stale calibration imports found"

- [ ] **Step 4: Commit any final fixes if needed**

If Step 3 found stale imports, fix them and commit:

```bash
git add -u
git commit -m "fix: remove stale calibration imports"
```
