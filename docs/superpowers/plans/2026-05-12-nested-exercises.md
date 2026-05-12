# Nested Exercise Directories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `code-review` resolve exercises that live at arbitrary depths under `exercises/` (e.g. `exercises/quantecon/python-programming/<slug>/`), surface the directory taxonomy in selection/stats screens, and relocate the `smoke-test` fixture out of `exercises/`.

**Architecture:** Add a `path` column (relative to `exercises/`) to `code_exercises`. `handle_add` derives this from the registered directory; the TUI resolves directories via `EXERCISES_DIR / path` instead of `EXERCISES_DIR / slug`. `MassedBrowseScreen` and `StatsScreen` render exercises grouped by category (the path with the leaf slug stripped). The due-queue screen keeps its date ordering but adds the category prefix to each row's label.

**Tech Stack:** Python 3.12, SQLite (via stdlib `sqlite3`), Textual TUI, pytest.

**Spec:** `docs/superpowers/specs/2026-05-12-nested-exercises-design.md`

---

## Task 1: Relocate smoke-test fixture

The `exercises/smoke-test/` directory was created as a build-time smoke test, not as a real exercise. Move it to `tests/code_review/fixtures/smoke-test/` so it stops appearing in workflows.

**Files:**
- Move: `exercises/smoke-test/` → `tests/code_review/fixtures/smoke-test/`
- Verify: no live code references

- [ ] **Step 1: Confirm no live references**

Run: `grep -rn "smoke-test\|smoke_test" src tests --include="*.py" --include="*.toml"`
Expected: empty output (the only references are in `docs/superpowers/plans/2026-05-10-code-review-tool.md`, which is archival).

- [ ] **Step 2: Move the directory**

```bash
mkdir -p tests/code_review/fixtures
git mv exercises/smoke-test tests/code_review/fixtures/smoke-test
```

- [ ] **Step 3: Verify no stray references and tests still pass**

Run: `uv run pytest tests/code_review -v`
Expected: all code_review tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/code_review/fixtures/smoke-test exercises
git commit -m "refactor(code-review): move smoke-test out of exercises/ to test fixtures"
```

---

## Task 2: Move EXERCISES_DIR constant to db.py

`EXERCISES_DIR` currently lives only in `tui.py`. The CLI will need it too, so move it into `db.py` alongside `DB_PATH` (both are repo-relative constants).

**Files:**
- Modify: `src/knowledge_base/code_review/db.py` (top of file)
- Modify: `src/knowledge_base/code_review/tui.py:39-40`

- [ ] **Step 1: Add EXERCISES_DIR to db.py**

In `src/knowledge_base/code_review/db.py`, replace:

```python
_REPO_ROOT = Path(__file__).parents[3]
DB_PATH = _REPO_ROOT / "data" / "code_exercises.db"
```

with:

```python
_REPO_ROOT = Path(__file__).parents[3]
DB_PATH = _REPO_ROOT / "data" / "code_exercises.db"
EXERCISES_DIR = _REPO_ROOT / "exercises"
```

- [ ] **Step 2: Import EXERCISES_DIR from db in tui.py**

In `src/knowledge_base/code_review/tui.py`, replace lines 27-40 so the import block reads:

```python
from knowledge_base.code_review.cli import handle_add
from knowledge_base.code_review.db import (
    DB_PATH,
    EXERCISES_DIR,
    get_all_exercises,
    get_due_exercises,
    init_db,
    record_grade,
    reset_all_exercises,
    reset_exercise,
)
from knowledge_base.code_review.leitner import schedule as leitner_schedule
from knowledge_base.code_review.runner import compute_side_by_side_diff, run_tests
```

…and delete the now-redundant `_REPO_ROOT` / `EXERCISES_DIR` definition at the top of the module:

```python
# DELETE THESE LINES (currently tui.py:39-40)
_REPO_ROOT = Path(__file__).parents[3]
EXERCISES_DIR = _REPO_ROOT / "exercises"
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass (pure refactor, no behavior change).

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/code_review/db.py src/knowledge_base/code_review/tui.py
git commit -m "refactor(code-review): move EXERCISES_DIR constant to db module"
```

---

## Task 3: Schema migration — add `path` column

Add a `path` column to `code_exercises` and migrate existing DBs.

**Files:**
- Modify: `src/knowledge_base/code_review/db.py`
- Test: `tests/code_review/test_db.py`

- [ ] **Step 1: Write failing migration test**

Add to `tests/code_review/test_db.py`:

```python
def test_init_db_adds_path_column_to_legacy_schema(tmp_path):
    """Pre-migration DB has no `path` column; init_db must add it and purge rows lacking a path."""
    import sqlite3
    from knowledge_base.code_review import db as db_mod

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE code_exercises (
            exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         TEXT    NOT NULL UNIQUE,
            title        TEXT    NOT NULL,
            source       TEXT    NOT NULL DEFAULT '',
            box          INTEGER NOT NULL DEFAULT 1,
            last_review  TEXT,
            due          TEXT,
            reps         INTEGER NOT NULL DEFAULT 0,
            added        TEXT    NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO code_exercises (slug, title, added) VALUES (?, ?, ?)",
        ("legacy-slug", "Legacy", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    migrated = db_mod.init_db(db_path)
    cols = {row[1] for row in migrated.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "path" in cols
    rows = migrated.execute("SELECT slug FROM code_exercises").fetchall()
    assert rows == []  # legacy row purged because path was unknown
    assert db_mod.LAST_MIGRATION_PURGE == ["legacy-slug"]


def test_init_db_fresh_has_path_column(tmp_path):
    from knowledge_base.code_review import db as db_mod

    conn = db_mod.init_db(tmp_path / "fresh.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "path" in cols
    assert db_mod.LAST_MIGRATION_PURGE == []
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run pytest tests/code_review/test_db.py::test_init_db_adds_path_column_to_legacy_schema -v`
Expected: FAIL — `path` not in columns / `LAST_MIGRATION_PURGE` doesn't exist.

- [ ] **Step 3: Implement migration in db.py**

In `src/knowledge_base/code_review/db.py`:

(a) Update the DDL:

```python
_DDL_EXERCISES = """
CREATE TABLE IF NOT EXISTS code_exercises (
    exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    path         TEXT    NOT NULL DEFAULT '',
    source       TEXT    NOT NULL DEFAULT '',
    box          INTEGER NOT NULL DEFAULT 1,
    last_review  TEXT,
    due          TEXT,
    reps         INTEGER NOT NULL DEFAULT 0,
    added        TEXT    NOT NULL
);
"""
```

(b) Add a module-level state list under the DDL constants:

```python
LAST_MIGRATION_PURGE: list[str] = []
```

(c) Replace `init_db` with the migrating version:

```python
def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    global LAST_MIGRATION_PURGE
    LAST_MIGRATION_PURGE = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    with conn:
        conn.execute(_DDL_EXERCISES)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
        if "path" not in cols:
            conn.execute("ALTER TABLE code_exercises ADD COLUMN path TEXT NOT NULL DEFAULT ''")
        purged = [
            row[0] for row in conn.execute(
                "SELECT slug FROM code_exercises WHERE path = ''"
            ).fetchall()
        ]
        if purged:
            conn.execute("DELETE FROM code_exercises WHERE path = ''")
            LAST_MIGRATION_PURGE = purged
    return conn
```

- [ ] **Step 4: Run test, verify it passes**

Run: `uv run pytest tests/code_review/test_db.py -v`
Expected: both new tests pass; existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/db.py tests/code_review/test_db.py
git commit -m "feat(code-review): add path column to code_exercises with auto-migration"
```

---

## Task 4: Update `add_exercise` to require `path`

`path` is required at the application layer (even though the DB defaults it to '') so we don't accidentally insert pathless rows that the next migration would purge.

**Files:**
- Modify: `src/knowledge_base/code_review/db.py`
- Test: `tests/code_review/test_db.py`

- [ ] **Step 1: Write failing test**

Add to `tests/code_review/test_db.py`:

```python
def test_add_exercise_persists_path(conn):
    eid = add_exercise(
        conn,
        slug="quantecon-3-1",
        title="Title",
        path="quantecon/python-programming/quantecon-3-1",
        source="quantecon-python",
    )
    ex = get_exercise_by_slug(conn, "quantecon-3-1")
    assert ex["path"] == "quantecon/python-programming/quantecon-3-1"
    assert ex["source"] == "quantecon-python"
```

- [ ] **Step 2: Update existing tests in `test_db.py` to pass path**

Replace the existing calls to `add_exercise` so each passes a path (use any plausible string):

```python
# test_add_exercise_returns_id
eid = add_exercise(conn, "my-slug", "My Title", path="my-slug", source="quantecon")

# test_get_exercise_by_slug
add_exercise(conn, "slug-a", "Title A", path="slug-a")

# test_get_due_exercises_includes_null_due
add_exercise(conn, "new-exercise", "New", path="new-exercise")

# test_get_due_exercises_excludes_future
eid = add_exercise(conn, "future-ex", "Future", path="future-ex")

# test_update_exercise_scheduling_increments_reps
eid = add_exercise(conn, "rep-test", "Rep Test", path="rep-test")

# test_insert_review_log
eid = add_exercise(conn, "log-test", "Log Test", path="log-test")
```

- [ ] **Step 3: Run tests, verify the new test fails (others may also fail until signature updated)**

Run: `uv run pytest tests/code_review/test_db.py -v`
Expected: failures due to unexpected `path=` kwarg.

- [ ] **Step 4: Update `add_exercise` signature**

In `src/knowledge_base/code_review/db.py`, replace `add_exercise`:

```python
def add_exercise(
    conn: sqlite3.Connection,
    slug: str,
    title: str,
    path: str,
    source: str = "",
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO code_exercises (slug, title, path, source, added) VALUES (?, ?, ?, ?, ?)",
        (slug, title, path, source, now),
    )
    conn.commit()
    return cur.lastrowid
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `uv run pytest tests/code_review/test_db.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/code_review/db.py tests/code_review/test_db.py
git commit -m "feat(code-review): require path when adding exercises"
```

---

## Task 5: CLI — store relative path on `code-review add`

`handle_add` must compute the path relative to `EXERCISES_DIR` and reject directories outside it.

**Files:**
- Modify: `src/knowledge_base/code_review/cli.py`
- Test: `tests/code_review/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/code_review/test_cli.py` (top imports already in place; we'll add `EXERCISES_DIR` monkeypatching since current tests use raw `tmp_path`):

```python
def test_handle_add_stores_relative_path(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    nested = exercises_root / "quantecon" / "python-programming" / "quantecon-3-1"
    nested.mkdir(parents=True)
    (nested / "problem.md").write_text("# Title\n")
    (nested / "test_solution.py").write_text("def test_pass(): pass\n")

    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)

    handle_add([str(nested)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "quantecon-3-1")
    assert ex["path"] == "quantecon/python-programming/quantecon-3-1"


def test_handle_add_stores_path_for_flat_exercise(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    flat = exercises_root / "flat-ex"
    flat.mkdir(parents=True)
    (flat / "problem.md").write_text("# Flat\n")
    (flat / "test_solution.py").write_text("def test_pass(): pass\n")

    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)

    handle_add([str(flat)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "flat-ex")
    assert ex["path"] == "flat-ex"


def test_handle_add_rejects_dir_outside_exercises_root(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    exercises_root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "problem.md").write_text("# X\n")
    (outside / "test_solution.py").write_text("def test_pass(): pass\n")

    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)

    with pytest.raises(SystemExit) as exc_info:
        handle_add([str(outside)], db_path=db_path)
    assert exc_info.value.code == 1
```

Also update existing tests in `test_cli.py` that registered exercises directly under `tmp_path`: each must place the exercise under a `tmp_path / "exercises"` root and monkeypatch `EXERCISES_DIR`. Concretely, rewrite the `ex_dir` fixture:

```python
@pytest.fixture
def ex_dir(tmp_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    d = exercises_root / "quantecon-3-3-fibonacci"
    d.mkdir(parents=True)
    (d / "problem.md").write_text("# Fibonacci Sequence\nImplement `fibonacci(n)`.\n")
    (d / "test_solution.py").write_text(
        "from submission import fibonacci\n"
        "def test_base(): assert fibonacci(0) == 0\n"
        "def test_known(): assert fibonacci(10) == 55\n"
    )
    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)
    return d
```

And for `test_handle_add_fails_on_missing_problem_md`, `test_handle_add_fails_on_missing_test_file`, `test_handle_add_falls_back_to_dirname_when_no_h1`, similarly create the exercise under a `tmp_path / "exercises"` root and monkeypatch — otherwise the new "outside exercises root" check will reject them before the missing-file checks fire.

Example refactor for `test_handle_add_fails_on_missing_problem_md`:

```python
def test_handle_add_fails_on_missing_problem_md(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    d = exercises_root / "incomplete-exercise"
    d.mkdir(parents=True)
    (d / "test_solution.py").write_text("# tests\n")
    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)
    with pytest.raises(SystemExit) as exc_info:
        handle_add([str(d)], db_path=db_path)
    assert exc_info.value.code == 1
```

Apply the same pattern to `test_handle_add_fails_on_missing_test_file` and `test_handle_add_falls_back_to_dirname_when_no_h1`.

- [ ] **Step 2: Run tests, verify failures**

Run: `uv run pytest tests/code_review/test_cli.py -v`
Expected: new path-related tests fail (no `path` column populated yet by CLI); some existing tests may also fail due to monkeypatching not matching old code.

- [ ] **Step 3: Update `cli.py`**

Replace `src/knowledge_base/code_review/cli.py` with:

```python
import argparse
import sqlite3
import sys
from pathlib import Path

from knowledge_base.code_review.db import (
    DB_PATH,
    EXERCISES_DIR,
    add_exercise,
    get_exercise_by_slug,
    init_db,
)


def _extract_title(problem_md: Path) -> str:
    for line in problem_md.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return problem_md.parent.name


def handle_add(args: list[str], db_path: Path | None = None) -> None:
    parser = argparse.ArgumentParser(prog="code-review add")
    parser.add_argument("exercise_dir", help="Path to exercise directory")
    parser.add_argument("--source", default="", help="Source identifier (e.g. 'quantecon-python')")
    parsed = parser.parse_args(args)

    exercise_dir = Path(parsed.exercise_dir).resolve()
    if not exercise_dir.is_dir():
        print(f"error: not a directory: {exercise_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        rel_path = exercise_dir.relative_to(EXERCISES_DIR.resolve())
    except ValueError:
        print(
            f"error: {exercise_dir} is not inside the exercises root ({EXERCISES_DIR})",
            file=sys.stderr,
        )
        sys.exit(1)

    problem_md = exercise_dir / "problem.md"
    test_file = exercise_dir / "test_solution.py"
    if not problem_md.exists():
        print(f"error: missing problem.md in {exercise_dir}", file=sys.stderr)
        sys.exit(1)
    if not test_file.exists():
        print(f"error: missing test_solution.py in {exercise_dir}", file=sys.stderr)
        sys.exit(1)

    slug = exercise_dir.name
    title = _extract_title(problem_md)
    conn = init_db(db_path or DB_PATH)

    if get_exercise_by_slug(conn, slug):
        print(f"error: exercise '{slug}' is already registered", file=sys.stderr)
        sys.exit(1)

    try:
        exercise_id = add_exercise(conn, slug, title, str(rel_path), parsed.source)
    except sqlite3.IntegrityError:
        print(f"error: exercise '{slug}' is already registered", file=sys.stderr)
        sys.exit(1)
    print(f"Added '{slug}' — {title} (id={exercise_id})")
```

Note: `EXERCISES_DIR` is imported at module level so monkeypatching `cli.EXERCISES_DIR` in tests works.

- [ ] **Step 4: Run tests, verify all pass**

Run: `uv run pytest tests/code_review/test_cli.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/cli.py tests/code_review/test_cli.py
git commit -m "feat(code-review): compute and store path relative to exercises root"
```

---

## Task 6: TUI runtime resolution — use `path` instead of `slug`

The two `EXERCISES_DIR / slug` sites in `tui.py` must use `path`.

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py:364`, `:399`

- [ ] **Step 1: Update `ReviewScreen.on_mount`**

Replace at `tui.py:364`:

```python
exercise_dir = EXERCISES_DIR / self._exercise["slug"]
```

with:

```python
exercise_dir = EXERCISES_DIR / self._exercise["path"]
```

- [ ] **Step 2: Update `ReviewScreen._open_editor`**

Replace at `tui.py:399`:

```python
exercise_dir = EXERCISES_DIR / self._exercise["slug"]
```

with:

```python
exercise_dir = EXERCISES_DIR / self._exercise["path"]
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass (no test currently exercises this resolution, but nothing should regress).

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/code_review/tui.py
git commit -m "fix(code-review): resolve exercise dirs by stored path, not slug"
```

---

## Task 7: Migration-purge notification in CLI and TUI

Make the migration purge visible to the user via stderr (CLI) and `notify` (TUI).

**Files:**
- Modify: `src/knowledge_base/code_review/cli.py`
- Modify: `src/knowledge_base/code_review/tui.py`

- [ ] **Step 1: Notify in CLI**

In `cli.py`, immediately after `conn = init_db(db_path or DB_PATH)`:

```python
from knowledge_base.code_review import db as _db_mod
if _db_mod.LAST_MIGRATION_PURGE:
    purged = ", ".join(_db_mod.LAST_MIGRATION_PURGE)
    print(
        f"notice: migrated DB and purged pre-migration rows: {purged}",
        file=sys.stderr,
    )
```

(Place the import at the top of the file alongside the existing imports.)

- [ ] **Step 2: Notify in TUI**

In `tui.py`, update `CodeReviewApp.on_mount`:

```python
class CodeReviewApp(App):
    def on_mount(self) -> None:
        from knowledge_base.code_review import db as _db_mod
        self._conn = init_db(DB_PATH)
        if _db_mod.LAST_MIGRATION_PURGE:
            purged = ", ".join(_db_mod.LAST_MIGRATION_PURGE)
            self.notify(
                f"Migrated DB — purged pre-migration rows: {purged}",
                severity="warning",
                timeout=10,
            )
        self.push_screen(ExerciseListScreen(self._conn))

    def on_unmount(self) -> None:
        self._conn.close()
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/code_review/cli.py src/knowledge_base/code_review/tui.py
git commit -m "feat(code-review): surface migration purge notice to user"
```

---

## Task 8: Add `category_of` helper and group_by_category builder

A shared helper used by both the browse and stats screens. Lives in `tui.py` (consumers are in this module) — module-private functions with unit tests.

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py`
- Create: `tests/code_review/test_tui_grouping.py`

- [ ] **Step 1: Write failing tests**

Create `tests/code_review/test_tui_grouping.py`:

```python
from knowledge_base.code_review.tui import category_of, group_by_category


def test_category_of_nested():
    assert category_of({"path": "quantecon/python-programming/quantecon-3-1"}) == (
        "quantecon/python-programming"
    )


def test_category_of_root_level():
    assert category_of({"path": "flat-ex"}) == ""


def test_category_of_empty_path_falls_back_to_root():
    assert category_of({"path": ""}) == ""


def test_group_by_category_orders_alphabetically_root_first():
    exercises = [
        {"path": "quantecon/intermediate/foo", "slug": "foo"},
        {"path": "quantecon/python-programming/bar", "slug": "bar"},
        {"path": "quantecon/python-programming/aaa", "slug": "aaa"},
        {"path": "loose", "slug": "loose"},
    ]
    grouped = group_by_category(exercises)
    assert [cat for cat, _ in grouped] == [
        "",
        "quantecon/intermediate",
        "quantecon/python-programming",
    ]
    aaa_bar = [e["slug"] for e in grouped[2][1]]
    assert aaa_bar == ["aaa", "bar"]  # slug-sorted within group
```

- [ ] **Step 2: Run tests, verify import error / failures**

Run: `uv run pytest tests/code_review/test_tui_grouping.py -v`
Expected: ImportError (`category_of` not defined).

- [ ] **Step 3: Add helpers to tui.py**

Insert near the top of `src/knowledge_base/code_review/tui.py`, after the imports and before `ExerciseListScreen`:

```python
def category_of(exercise: dict) -> str:
    """Return the category for an exercise — its path with the leaf slug stripped.

    Root-level exercises return "".
    """
    path = exercise.get("path") or ""
    parts = path.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def group_by_category(exercises: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group exercises by category; root category ("") first, then alphabetical.

    Within each group, exercises are sorted by slug.
    """
    by_cat: dict[str, list[dict]] = {}
    for ex in exercises:
        by_cat.setdefault(category_of(ex), []).append(ex)
    ordered = sorted(by_cat.keys(), key=lambda c: (c != "", c))
    return [(cat, sorted(by_cat[cat], key=lambda e: e["slug"])) for cat in ordered]
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `uv run pytest tests/code_review/test_tui_grouping.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/tui.py tests/code_review/test_tui_grouping.py
git commit -m "feat(code-review): add category_of and group_by_category helpers"
```

---

## Task 9: Apply grouping to MassedBrowseScreen

Render the browse list with non-selectable header rows between category groups.

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py` (MassedBrowseScreen)

- [ ] **Step 1: Update `MassedBrowseScreen.compose` CSS for headers**

Append to the screen's CSS (currently `MassedBrowseScreen.CSS`):

```python
CSS = """
#browse-header { margin: 1 2; }
#browse-notice { margin: 0 2 1 2; color: $warning; }
.category-header { color: $text-muted; padding: 0 1; }
"""
```

- [ ] **Step 2: Update `_render_list` to insert headers**

Replace the body of `MassedBrowseScreen._render_list`:

```python
def _render_list(self, preserve_id: int | None = None) -> None:
    lv = self.query_one("#browse-list", ListView)
    if preserve_id is None and lv.highlighted_child is not None:
        if hasattr(lv.highlighted_child, "_exercise"):
            preserve_id = lv.highlighted_child._exercise["exercise_id"]
    lv.clear()
    ids = self._selected_ids()
    target_index: int | None = None
    flat_index = 0
    for cat, group in group_by_category(self._exercises):
        header_label = cat if cat else "(root)"
        header = ListItem(Label(f"── {header_label} ──", classes="category-header"))
        header.disabled = True
        lv.append(header)
        flat_index += 1
        for ex in group:
            marker = "[✓]" if ex["exercise_id"] in ids else "[ ]"
            due_str = ex["due"][:10] if ex["due"] else "new"
            label = (
                f"{marker} [{due_str}]  {ex['slug']}  —  {ex['title']}  "
                f"(box {ex['box']}, reps {ex['reps']})"
            )
            item = ListItem(Label(label))
            item._exercise = ex  # type: ignore[attr-defined]
            lv.append(item)
            if preserve_id is not None and ex["exercise_id"] == preserve_id:
                target_index = flat_index
            flat_index += 1
    if target_index is not None:
        lv.index = target_index
```

Note: `disabled=True` on a `ListItem` prevents focus (Textual >= 0.40); the existing `on_key` already guards with `hasattr(item, "_exercise")` so even if focus does land on a header by some keypath, space/enter no-op.

- [ ] **Step 3: Manually verify**

Register at least two exercises in different categories (e.g. one in `quantecon/python-programming/`, one at the root). Run:

```bash
uv run code-review
```

Press `m` to enter MassedBrowseScreen. Expected: headers `── (root) ──` and `── quantecon/python-programming ──` appear above their respective items; cursor skips over headers.

(If no exercises are registered yet, register two from existing dirs to test:
```bash
uv run code-review add exercises/quantecon/python-programming/quantecon-3-1
```
Then add a second, e.g. by re-creating a tiny flat exercise temporarily, or skip the manual verify and rely on the unit-tested helper.)

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/tui.py
git commit -m "feat(code-review): group MassedBrowseScreen by exercise category"
```

---

## Task 10: Apply grouping to StatsScreen

Same treatment as the browse screen.

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py` (StatsScreen)

- [ ] **Step 1: Update `StatsScreen.CSS` to include `.category-header`**

```python
CSS = """
#stats-header { margin: 1 2; }
#confirm-bar  { margin: 0 2 1 2; color: $warning; }
.hidden { display: none; }
.category-header { color: $text-muted; padding: 0 1; }
"""
```

- [ ] **Step 2: Update `StatsScreen._reload`**

Replace the body:

```python
def _reload(self) -> None:
    exercises = get_all_exercises(self._conn)
    lv = self.query_one("#stats-list", ListView)
    lv.clear()
    for cat, group in group_by_category(exercises):
        header_label = cat if cat else "(root)"
        header = ListItem(Label(f"── {header_label} ──", classes="category-header"))
        header.disabled = True
        lv.append(header)
        for ex in group:
            due  = ex["due"][:10]         if ex["due"]         else "—"
            last = ex["last_review"][:10] if ex["last_review"] else "never"
            label = (
                f"box {ex['box']}  reps {ex['reps']:>3}  "
                f"last {last}  next {due}    {ex['slug']}"
            )
            item = ListItem(Label(label))
            item._exercise = ex  # type: ignore[attr-defined]
            lv.append(item)
    n = len(exercises)
    self.query_one("#stats-header", Static).update(
        f"{n} exercise(s)   r = reset selected   R = reset all"
    )
```

- [ ] **Step 3: Confirm reset actions still work**

`action_reset_one` calls `lv.highlighted_child._exercise`; the `hasattr` guard prevents triggering on headers. Visually check: pressing `r` while a header is highlighted does nothing.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/tui.py
git commit -m "feat(code-review): group StatsScreen by exercise category"
```

---

## Task 11: Add category prefix to due-queue labels

The due queue stays date-ordered; we just enrich the label with category context.

**Files:**
- Modify: `src/knowledge_base/code_review/tui.py` (ExerciseListScreen._reload)

- [ ] **Step 1: Update label construction**

In `ExerciseListScreen._reload`, replace:

```python
label = f"[{due_str}]  {ex['slug']}  —  {ex['title']}  (box {ex['box']}, reps {ex['reps']})"
```

with:

```python
cat = category_of(ex)
prefix = f"{cat} · " if cat else ""
label = (
    f"[{due_str}]  {prefix}{ex['slug']}  —  {ex['title']}  "
    f"(box {ex['box']}, reps {ex['reps']})"
)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/code_review -v`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/knowledge_base/code_review/tui.py
git commit -m "feat(code-review): show category prefix in due-queue labels"
```

---

## Task 12: End-to-end verification

Register a real nested exercise and run through the full flow once.

- [ ] **Step 1: Re-register exercises**

Since the live DB's only row was purged by the migration in Task 3, re-add one nested exercise:

```bash
uv run code-review add exercises/quantecon/python-programming/quantecon-3-1
```

Expected stdout: `Added 'quantecon-3-1' — <Title> (id=…)`.

- [ ] **Step 2: Verify path persisted**

```bash
sqlite3 data/code_exercises.db "SELECT slug, path FROM code_exercises;"
```

Expected: `quantecon-3-1|quantecon/python-programming/quantecon-3-1`.

- [ ] **Step 3: Launch TUI and click through**

```bash
uv run code-review
```

Verify:
1. Due-queue label shows `quantecon/python-programming · quantecon-3-1 — <Title>`.
2. Press `m` — browse screen shows `── quantecon/python-programming ──` header above the exercise.
3. Press `s` from the main screen — stats shows the same grouped layout.
4. Select the exercise, press Enter to open editor, write a no-op, save and quit. Test results appear (FAIL is expected for a no-op). Grade `Again`. The exercise re-appears in the queue with its date updated.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest`
Expected: all ~390+ tests pass.

- [ ] **Step 5: No commit needed (verification only)**

If verification surfaced any regression, return to the relevant task and fix before declaring done.

---

## Summary of files touched

- `src/knowledge_base/code_review/db.py` — `EXERCISES_DIR` constant, `path` column, migration, `add_exercise(path=…)`
- `src/knowledge_base/code_review/cli.py` — derive `rel_path`, reject outside-root dirs, migration notice
- `src/knowledge_base/code_review/tui.py` — `path`-based resolution, migration notify, `category_of` + `group_by_category`, grouped browse/stats, due-queue label prefix
- `tests/code_review/test_db.py` — migration tests, updated `add_exercise` calls
- `tests/code_review/test_cli.py` — `EXERCISES_DIR` monkeypatching, path-storage assertions, outside-root rejection
- `tests/code_review/test_tui_grouping.py` — new unit tests for grouping helpers
- `tests/code_review/fixtures/smoke-test/` — moved from `exercises/smoke-test/`
