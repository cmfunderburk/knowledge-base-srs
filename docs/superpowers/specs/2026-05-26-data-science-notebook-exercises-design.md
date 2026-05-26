# Data-Science Notebook Exercises (`uv run data-science`)

**Status:** Approved for implementation
**Date:** 2026-05-26

## Problem

The current `code-review` harness (`problem.md` + `solution.py` + `test_solution.py`, single `$EDITOR` submission, pytest run) handles algorithmic and pure-math exercises well — see the existing `exercises/algos/` and `exercises/quantecon/python-programming/` directories. It does not handle the workflows taught in Ch 2-6 of `intro.quantecon.org` (Long-Run Growth, Business Cycles, Inflation in History, Income and Wealth Inequality, A Single-Good Market), which are multi-step data-science pipelines: retrieve a dataset, clean it, transform it, plot it, interpret the plot.

Three reasons the existing shape mis-fits these chapters:

1. **No notebook-style feedback loop.** Real data work alternates editing with intermediate inspection (`df.head()`, render a small plot, decide what to do next). A single `$EDITOR` session forces the user to write the whole pipeline blind.
2. **No first-class plot grading.** `assert_frame_equal` covers transforms but says nothing about whether the resulting figure has the right axis scale, line count, labels.
3. **Production-tool drift.** The chapters are written in Jupyter; data work in practice happens in Jupyter; the user's existing study workflow uses Jupyter Lab. Practicing in `$EDITOR` doesn't transfer.

Goal: extend the knowledge-base repo with a sibling workflow that lets the user practice Ch 2-6 patterns in a Jupyter-native, FSRS-scheduled, deliberate-practice loop. Use synthetic data so exercises are deterministic and offline.

## Non-goals

- **No** changes to the existing `code-review` flow, scheduler, or runner. The existing trio convention and pytest-driven loop stay exactly as they are.
- **No** real-data retrieval (FRED / World Bank / Yahoo). Exercises run against synthetic data from a shared generator module; the user practices the *patterns* without the network dependency or non-determinism.
- **No** pixel-level plot comparison. Plot grading is structural assertions on `matplotlib.axes.Axes` objects (axis scale, line count, labels), not image diffs.
- **No** custom notebook-execution machinery beyond what `testbook` provides. Headless execution and namespace inspection are delegated to that library.
- **No** in-TUI cell editing. The user works in real Jupyter Lab; the TUI handles launch, signal-done, run-tests, grade.
- **No** authoring all of Ch 2-6 upfront. The thin slice ships one Ch 2 capstone exercise that validates the architecture end-to-end. Subsequent exercises are authored chapter-by-chapter in later sessions.
- **No** mid-session persistence of `submission.ipynb` across sessions (initially). Ephemeral, like the existing `submission.py`. Revisit if a single capstone routinely takes multiple sittings.

## Approach

Two sibling entry points share scheduling and DB; only the runner and review screen differ:

- `uv run code-review` → existing flow, unchanged. Runs `kind='code'` exercises.
- `uv run data-science` → new flow. Runs `kind='notebook'` exercises.

Both flows write to `data/code_exercises.db` via the same `db.py` and `scheduler.py`. A new `kind` column on the `code_exercises` table distinguishes the two; the launcher dispatches to the right review screen based on `kind`.

### Why this factoring

Scheduling, grading, and review-log machinery are pure — they don't care which runner produced the verdict. Splitting on the runner boundary keeps the shared core untouched and confines notebook-specific complexity to two new modules (`notebook_runner.py`, `notebook_tui.py`) plus a shared synthetic-data package (`datasets/`).

### Rejected alternatives

The design choice was between three notebook-style approaches; see the brainstorming session for full tradeoffs. Summary:

| Option | Rejected because |
|---|---|
| **A.** Single submission with multiple named functions; reuse existing runner | Lowest notebook fidelity; forces functional-decomposition shape upfront; no intermediate `df.head()` inspection. Teaches a real skill but the wrong one for the stated goal. |
| **B.** Multi-cell submission in TUI with shared-namespace `exec`; stdout streamed to TUI | Real notebook feel, but requires building cell-walking machinery from scratch when Jupyter already has it. Larger build than Option C with worse fidelity (no autocomplete, no inline plots, no kernel introspection). |
| **C.** Real `.ipynb` driven by Jupyter Lab + `testbook` — **chosen** | Delegates cell-walking to the actual production tool. Native inline plots, autocomplete, kernel introspection, mid-cell `df.head()`. Smaller build than Option B because most of the work lives in tools we don't maintain. |

## Architecture

```
                                                ┌─ ReviewScreen (existing)
exercises/<slug>/{problem.md, *.py, ...}  ──────┤
                                                └─ uv run code-review

                                                ┌─ NotebookReviewScreen (new)
exercises/<slug>/{problem.md, *.ipynb, ...} ────┤
                                                └─ uv run data-science

                          shared:
                            data/code_exercises.db
                              (rows carry `kind` column: 'code' | 'notebook')
                            src/knowledge_base/code_review/scheduler.py  (unchanged)
                            src/knowledge_base/code_review/db.py         (+ kind column)
                            shared GradeButtons Textual widget
```

### Module layout

```
src/knowledge_base/code_review/
    scheduler.py                      unchanged
    db.py                             + kind column; auto-discovery extended
    runner.py                         unchanged
    tui.py                            unchanged except: extract GradeButtons to widgets.py
    widgets.py                        NEW  — shared GradeButtons Textual widget

    notebook_runner.py                NEW  — spawn jupyter, wait, run testbook, diff
    notebook_tui.py                   NEW  — NotebookReviewScreen + data-science entry point

    datasets/                         NEW  — shared synthetic-data generators
        __init__.py                      re-exports all generators
        gdp.py                           gdp_panel(seed, ...)
        population.py                    population_panel(seed, ...)
        (chapter generators added as authored)
```

### Entry points (`pyproject.toml`)

```toml
[project.scripts]
review-gen = "knowledge_base.srs.generation_tui:main"
gen-import = "knowledge_base.srs.generation_import:main"
gen-import-md = "knowledge_base.srs.md_importer:main"
gen-import-csv = "knowledge_base.srs.csv_importer:main"
code-review = "knowledge_base.code_review.tui:main"
data-science = "knowledge_base.code_review.notebook_tui:main"     # NEW
```

## Exercise directory convention

```
exercises/quantecon/intro/<slug>/
    problem.md            # task description; rendered in TUI before launching Jupyter
    starter.ipynb         # template the user works in
    solution.ipynb        # reference; revealed as cell-source diff after grading
    test_solution.py      # pytest + testbook; asserts on submission.ipynb
    submission.ipynb      # gitignored; copied from starter on launch; deleted in finally
```

**`problem.md`** — same convention as code exercises. First H1 is the title. Body describes the pipeline, lists what each cell should produce, names the canonical variable names tests will reference, and names which generators the Setup cell uses.

**`starter.ipynb`** — markdown cells carrying the per-cell prose interleaved with empty code cells. A pinned `# === Setup (do not edit) ===` cell at the top imports from `knowledge_base.code_review.datasets` and binds the synthetic input data. The user works in the empty code cells below.

**`solution.ipynb`** — fully worked. Same Setup cell as starter. Used for two things: (a) sanity check that the test file passes against a correct solution (the `test_solution_passes` meta-test in every exercise); (b) source-cell diff shown to the user after grading.

**`test_solution.py`** — uses `testbook` to execute `submission.ipynb` headlessly. Tests assert on namespace bindings via `tb.ref("name")` and on figure structure via `tb.ref("ax").get_*()`. Tests are grouped per-cell via naming convention (`test_cell2_...`) so failure localizes to the cell the user should look at.

**`submission.ipynb`** — gitignored alongside `submission.py` in the repo `.gitignore`. Created on exercise launch by `shutil.copy(starter, submission)`; deleted in a `finally` after grading completes.

### Auto-discovery

`sync_exercises_from_disk()` in `db.py` walks `exercises/`. Extend its file-shape detection:

- Dir contains `problem.md` + `solution.py` + `test_solution.py` → register `kind='code'`
- Dir contains `problem.md` + `solution.ipynb` + `starter.ipynb` + `test_solution.py` → register `kind='notebook'`
- Dir contains both `solution.py` and `solution.ipynb` → log error, skip (ambiguous)
- Dir contains `problem.md` + `solution.ipynb` + `test_solution.py` but no `starter.ipynb` → log error, skip (notebook file set is incomplete; starter is required for the copy-to-submission step)

### Migration

Existing rows in `code_exercises` get `kind='code'` via a one-shot ALTER + UPDATE:

```sql
ALTER TABLE code_exercises ADD COLUMN kind TEXT NOT NULL DEFAULT 'code';
```

Default 'code' covers all existing rows; new notebook discoveries explicitly write `kind='notebook'`. No data migration needed beyond schema change.

## Datasets module

### Generator contract

Every generator is a pure function:

```python
def gdp_panel(
    seed: int,
    *,
    n_countries: int = 8,
    year_start: int = 1820,
    year_end: int = 2020,
) -> pd.DataFrame:
    """Annual nominal GDP for n_countries from year_start to year_end inclusive.

    Returns a DataFrame indexed by year (int), columns are country codes
    (str, ISO3-like fakes: 'USA', 'GBR', 'DEU', ...), values are floats.
    Includes a few plausibly-placed missing values per country.
    Deterministic for a given seed.
    """
```

Three rules across all generators:

1. **Pure.** No I/O, no caching, no global state. Use `numpy.random.default_rng(seed)`.
2. **Shape-faithful.** Datasets look like the real domain — named columns, plausible scales, structural features (missing data, breaks, heteroskedasticity). Idioms learned on synthetic transfer to real data.
3. **Small by default.** Defaults produce ~100-200 rows so headless notebook execution is fast (testbook re-runs every test session). Params let exercises scale up if a particular pattern needs it.

### Thin-slice scope

Only what the Ch 2 capstone needs:

- `gdp_panel(seed, ...)` — annual GDP by country (described above)
- `population_panel(seed, ...)` — annual population by country, aligned columns and index to `gdp_panel`

### Growth path

As subsequent chapters are authored, the module accretes:

- Ch 3 (Business Cycles) → `quarterly_macro(seed, ...)` — GDP, unemployment, recession-flag columns
- Ch 4 (Inflation) → `cpi_panel(seed, ...)` — with one or two hyperinflation episodes
- Ch 5 (Inequality) → `income_distribution(seed, ...)` — cross-section
- Ch 6 (Market) → `supply_demand_pairs(seed, ...)`

Each chapter's first exercise can add or extend one generator. Generators don't depend on each other.

### Discovery

`datasets/__init__.py` re-exports every generator so problem.md and Setup cells use the short import path:

```python
from knowledge_base.code_review.datasets import gdp_panel, population_panel
```

The function name *is* the API.

### Generator tests

Each generator gets a small unit test in `tests/datasets/`:

- Same seed → identical frame
- Default params produce non-empty output of expected shape
- Structural columns are present
- Different seeds produce different data

Cheap insurance against future generator drift breaking dozens of exercises.

## Runner mechanics (`notebook_runner.py`)

### Lifecycle

```
launch_session(exercise_dir) -> SessionHandle
  │
  ├─ 1. shutil.copy(starter.ipynb, submission.ipynb)
  │
  ├─ 2. proc = subprocess.Popen(
  │        ["jupyter", "lab", "submission.ipynb",
  │         "--ServerApp.port=0",         # OS picks a free port
  │         "--ServerApp.open_browser=True"],
  │        cwd=exercise_dir,
  │        stdout=subprocess.PIPE,        # captured so we can extract the URL
  │        stderr=subprocess.STDOUT,
  │        start_new_session=True,
  │    )
  │    # TUI surfaces the URL by tailing proc.stdout in a background task,
  │    # so if browser auto-launch fails the user can copy the URL manually.
  │
  ├─ 3. return SessionHandle(proc, exercise_dir) to TUI
  │     (TUI shows "Jupyter open…" + press-Enter prompt with confirmation modal)

run_tests(handle) -> TestResult
  │
  ├─ result = subprocess.run(
  │      ["pytest", "test_solution.py", "--tb=short", "-q"],
  │      cwd=handle.exercise_dir,
  │      capture_output=True,
  │      timeout=120,
  │  )
  └─ return TestResult(passed=result.returncode == 0, output=...)

compute_notebook_diff(handle) -> str
  │
  └─ Unified diff of code-cell sources only (markdown cells skipped),
     using nbformat.read() to extract cell.source from submission.ipynb
     and solution.ipynb.

cleanup_session(handle)  [always called in finally]
  │
  ├─ handle.proc.terminate()
  ├─ try: handle.proc.wait(timeout=5)
  ├─ except TimeoutExpired: handle.proc.kill()
  └─ (handle.exercise_dir / "submission.ipynb").unlink(missing_ok=True)
```

### Subprocess management

Spawning as `Popen` (not `run`) is essential — Jupyter Lab is a long-running server. The TUI doesn't wait on it; the user does. `start_new_session=True` isolates the Jupyter process group from the TUI's signal handling. `--ServerApp.port=0` lets the OS pick a free port (avoids conflicts with any user-launched Jupyter). Capturing stdout/stderr lets the TUI surface the access URL if browser auto-launch fails.

### Why `cwd=exercise_dir`

Jupyter's working directory becomes the exercise dir so the user's notebook can `import` from the exercise dir naturally. The `datasets` module is imported via the installed package path, so it works from any cwd.

### Why separate-process pytest

Tests run as a separate `pytest` subprocess (not in-process) for the same reason `runner.py` does it for code exercises: clean import state, no testbook-kernel leakage into the TUI process.

### Failure modes

| Failure | Handling |
|---|---|
| `jupyter` not installed | Detect at session start; raise with install hint before copying starter. |
| Port conflict | `--ServerApp.port=0` lets the OS pick a free port. |
| User closes browser but Jupyter keeps running | Enter in TUI → tests run against last-saved `submission.ipynb` → cleanup terminates the orphan server. |
| User presses Enter before saving in Jupyter | Tests run against the previous save (possibly unmodified starter) → tests fail loudly → user retries. Confirmation modal mitigates accidental case. |
| `testbook` kernel hangs mid-execution | pytest timeout (120s) fires; surface as test failure with "kernel hung — retry?" hint. |
| Jupyter spawned but `Popen` returns before server is ready | Acceptable — user waits a beat for browser to open. No readiness polling. |
| User abandons mid-session (Ctrl-C in TUI / Abandon button) | TUI-level handler calls `cleanup_session()`; same finally path. No grade recorded. |

## TUI (`notebook_tui.py`)

### `NotebookReviewScreen`

```
┌─ NotebookReviewScreen ────────────────────────────────────┐
│ # Long-Run Growth: GDP-per-capita pipeline                │
│                                                            │
│ (rendered problem.md)                                     │
│                                                            │
│ [ Launch Jupyter ]                                         │
└────────────────────────────────────────────────────────────┘
        │  press button
        ▼
┌────────────────────────────────────────────────────────────┐
│  Jupyter running on http://localhost:PORT/                 │
│  Working dir: exercises/quantecon/intro/long-run-growth/   │
│                                                            │
│  Work in your browser. Save when done.                     │
│  Press [Enter] to run tests against your saved notebook.   │
│                                                            │
│  [ Run tests now ]   [ Abandon session ]                   │
└────────────────────────────────────────────────────────────┘
        │  Enter key
        ▼
┌─ Confirm ──────────────────────────────┐
│ Run tests against submission.ipynb?     │
│ Make sure you've saved in Jupyter.      │
│                                         │
│      [ Cancel (default) ]   [ Run ]     │
└─────────────────────────────────────────┘
        │  Run
        ▼
(pytest output, then notebook source diff, then GradeButtons widget)
        │  grade
        ▼
db.record_grade()  →  cleanup_session()  →  back to exercise list
```

### Confirmation modal defaults to Cancel

A stray Enter dismisses the modal harmlessly. Explicit Right-arrow + Enter (or click) triggers the test run. Mirrors the safer default for actions with side effects.

### Abandon Session button

Equivalent to Ctrl-C but explicit and discoverable. Runs the same `finally` cleanup (terminate Jupyter, delete `submission.ipynb`). Returns to exercise list. No grade recorded.

### Exercise list screen

A thin parallel of `ExerciseListScreen`, filtered to `kind='notebook'`. Same FSRS-due-list logic; only the row click handler differs (launches `NotebookReviewScreen`). Refactoring `ExerciseListScreen` into a generic + two thin specializations is deferred — the thin slice ships as a parallel screen; refactor later if both lists grow features in parallel.

### Shared `GradeButtons`

Extract the Again/Hard/Good/Easy widget from `tui.py` into a new `widgets.py`. Both `ReviewScreen` and `NotebookReviewScreen` import from there. Only refactor in the existing TUI as part of the thin slice.

## Test pattern (`test_solution.py` per exercise)

### Module-scoped testbook fixture

The notebook runs once per test session; each test asserts against the resulting kernel state.

```python
import pytest
from testbook import testbook

@pytest.fixture(scope="module")
def tb():
    with testbook("submission.ipynb", execute=True) as tb:
        yield tb
```

### Canonical variable names as interface

`problem.md` specifies the canonical name for each cell's output ("your per-capita frame must be named `gdp_per_capita`"). Tests reference those names via `tb.ref("gdp_per_capita")`. If the user names it differently, tests fail at `tb.ref(...)` with a clear "name not defined" message. The constraint is pedagogically useful: variables are an interface, not internal.

### Per-cell failure localization via test naming

The notebook runs end-to-end, but test names carry the cell number (`test_cell2_per_capita_shape`, `test_cell3_growth_formula`). When test 3 fails, the user knows where to look. No per-cell exec machinery needed.

### Axes assertions are kernel-side

`tb.ref("ax").get_yscale()` runs the method in the kernel and returns the result. Works for line count, axis labels, scale, ticks, tick labels — every structural invariant we care about. Pixel-level comparison is out of scope.

### Assert invariants, not surface

Tests describe *what the chapter is teaching*, not *what the reference solution happens to do*. Don't assert exact title text, color choices, linewidth. A user who picks different colors but draws the correct log-y multi-country plot passes.

### Permissive on extra cells

Users can add debugging cells (`print(df.head())`, scratch plots) freely. testbook executes the notebook as-is; extra cells run and are ignored unless they mutate canonical variables in breaking ways.

### One sanity test in every exercise

```python
def test_setup_cell_unchanged(tb):
    src = tb.cells[0].source
    assert "gdp_panel(seed=42)" in src
    assert "population_panel(seed=42)" in src
```

Fires immediately with a clear message if the user edited the seed or the dataset call, rather than producing mysterious downstream failures.

### Meta-test in every exercise

```python
def test_solution_passes():
    """The reference solution.ipynb must pass all assertions above."""
    import shutil, subprocess, pathlib
    here = pathlib.Path(__file__).parent
    shutil.copy(here / "solution.ipynb", here / "submission.ipynb")
    try:
        r = subprocess.run(
            ["pytest", str(here), "-q",
             "--deselect", f"{__file__}::test_solution_passes"],
            capture_output=True,
        )
        assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()
    finally:
        (here / "submission.ipynb").unlink(missing_ok=True)
```

Runs in CI / on every `pytest tests/`. Fires if the test file drifts from what `solution.ipynb` produces. `--deselect` keeps it from recursing into itself.

## Thin slice: Ch 2 Long-Run Growth capstone

### Slug

`exercises/quantecon/intro/long-run-growth/`

### Pedagogical target

Chain the four idioms that define Ch 2: align two frames, divide frames, summarize a long series, plot on a log axis with one line per country.

### Cell structure (in starter.ipynb)

```
# === Setup (do not edit) ===
from knowledge_base.code_review.datasets import gdp_panel, population_panel
gdp = gdp_panel(seed=42)        # DataFrame: years × 8 countries, with NaNs
pop = population_panel(seed=42) # DataFrame: years × 8 countries, aligned columns

# Cell 1 — Align and clean
# Produce two frames `gdp_clean` and `pop_clean` covering only the years where
# BOTH gdp and pop have data for ALL countries. Same shape, same index, same columns.

(empty code cell)

# Cell 2 — Per-capita GDP
# Compute per-capita GDP using gdp_clean and pop_clean.
# Bind the result to `gdp_per_capita` (DataFrame, same shape as the cleaned frames).

(empty code cell)

# Cell 3 — Long-run annualized growth
# Compute the annualized growth rate per country over the full cleaned window:
#     g = (gdp_per_capita.iloc[-1] / gdp_per_capita.iloc[0]) ** (1 / n_years) - 1
# Bind the result to `long_run_growth` (Series, indexed by country code).

(empty code cell)

# Cell 4 — Plot on a log y-axis
# Create a matplotlib figure. Plot `gdp_per_capita` with one line per country
# on a log y-axis. Label x-axis "Year", y-axis "GDP per capita (log scale)".
# Add a legend. Bind the Axes to `ax`.

(empty code cell)
```

### Canonical names

| Cell | Variable | Type | What's tested |
|---|---|---|---|
| 1 | `gdp_clean`, `pop_clean` | DataFrame | Alignment shape, NaN-free post-clean |
| 2 | `gdp_per_capita` | DataFrame | Division logic against a recomputation |
| 3 | `long_run_growth` | Series | Annualization formula correctness |
| 4 | `ax` | matplotlib.axes.Axes | yscale=='log', line count == 8, axis labels |

### Test file sketch

```python
import pytest
from testbook import testbook
import pandas as pd


@pytest.fixture(scope="module")
def tb():
    with testbook("submission.ipynb", execute=True) as tb:
        yield tb


def test_setup_cell_unchanged(tb):
    src = tb.cells[0].source
    assert "gdp_panel(seed=42)" in src
    assert "population_panel(seed=42)" in src


def test_cell1_no_nans(tb):
    assert not tb.ref("gdp_clean").resolve().isna().any().any()
    assert not tb.ref("pop_clean").resolve().isna().any().any()


def test_cell1_alignment(tb):
    gdp_c = tb.ref("gdp_clean").resolve()
    pop_c = tb.ref("pop_clean").resolve()
    assert gdp_c.shape == pop_c.shape
    assert (gdp_c.index == pop_c.index).all()
    assert (gdp_c.columns == pop_c.columns).all()


def test_cell2_division(tb):
    gdp_c = tb.ref("gdp_clean").resolve()
    pop_c = tb.ref("pop_clean").resolve()
    gpc = tb.ref("gdp_per_capita").resolve()
    pd.testing.assert_frame_equal(gpc, gdp_c / pop_c)


def test_cell3_growth_formula(tb):
    gpc = tb.ref("gdp_per_capita").resolve()
    actual = tb.ref("long_run_growth").resolve()
    n_years = len(gpc.index) - 1
    expected = (gpc.iloc[-1] / gpc.iloc[0]) ** (1 / n_years) - 1
    pd.testing.assert_series_equal(actual, expected, check_names=False)


def test_cell4_log_yaxis(tb):
    assert tb.ref("ax").get_yscale() == "log"


def test_cell4_line_per_country(tb):
    assert len(tb.ref("ax").get_lines()) == 8


def test_cell4_axis_labels(tb):
    assert tb.ref("ax").get_xlabel() == "Year"
    assert "log scale" in tb.ref("ax").get_ylabel().lower()


def test_solution_passes():
    import shutil, subprocess, pathlib
    here = pathlib.Path(__file__).parent
    shutil.copy(here / "solution.ipynb", here / "submission.ipynb")
    try:
        r = subprocess.run(
            ["pytest", str(here), "-q",
             "--deselect", f"{__file__}::test_solution_passes"],
            capture_output=True,
        )
        assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()
    finally:
        (here / "submission.ipynb").unlink(missing_ok=True)
```

## Dependencies

Added to `pyproject.toml`:

- `jupyterlab` — the production tool the user works in
- `testbook` — headless notebook execution and namespace inspection
- `nbformat` — read/write notebook JSON for source-cell diff
- `nbclient` — pulled in transitively by testbook; pinning isn't necessary

`matplotlib`, `pandas`, `numpy` — already installed for the broader project; verify in `pyproject.toml`.

`.gitignore` additions:

```
exercises/**/submission.ipynb
```

(alongside the existing `exercises/**/submission.py` entry)

## Acceptance criteria

The thin slice is done when, in order:

1. `uv run data-science` launches a TUI listing the one Ch 2 capstone exercise.
2. Selecting it renders `problem.md`, launches Jupyter Lab on `submission.ipynb` in the exercise dir.
3. The user working in the notebook, saving, returning to the TUI, and confirming the modal runs tests against `submission.ipynb`.
4. A correct solution produces pytest green; the source-cell diff of `submission.ipynb` vs `solution.ipynb` displays; grading writes to `data/code_exercises.db`; the exercise re-appears on its FSRS-scheduled due date.
5. An incorrect solution produces specific per-cell failures naming the wrong cell (via `test_cell2_*`, `test_cell3_*` test names).
6. `pytest tests/` (project-wide) passes, including:
   - `tests/datasets/` unit tests for `gdp_panel` and `population_panel` (determinism, shape, structural columns)
   - `tests/code_review/test_notebook_runner.py` covering `launch_session` / `run_tests` / `compute_notebook_diff` / `cleanup_session` (using a tiny test-fixture notebook in `tests/fixtures/`, not the real Ch 2 exercise)
   - `test_solution_passes` in the new exercise (the meta-test that runs `solution.ipynb` through `test_solution.py`)
   - All existing tests continue to pass
7. `submission.ipynb` is gitignored; no stray files left after a session (whether passed, failed, or abandoned).
8. Existing `uv run code-review` and all existing exercises behave identically to before (regression check).

## Out of scope for this spec (deferred to later sessions)

- Authoring exercises beyond the one Ch 2 capstone
- Datasets module entries beyond `gdp_panel` and `population_panel`
- Mid-session persistence of `submission.ipynb` across sittings
- Unified exercise list combining `kind='code'` and `kind='notebook'` rows
- Per-cell micro exercises (vs. capstones) in the data-science track — the two-track design lives in the design vocabulary; micro exercises are deferred until the capstone shape is validated in use
- Image-diff plot grading
- Custom Jupyter Lab extensions or kernel configuration
