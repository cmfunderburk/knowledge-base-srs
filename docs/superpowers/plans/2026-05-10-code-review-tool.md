# Code Review Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `uv run code-review` to knowledge-base — a Leitner-scheduled spaced practice tool for programming exercises that shows a problem statement, opens `$EDITOR` for the user's solution, runs pytest, shows a diff against the reference, and records a grade.

**Architecture:** A new `src/knowledge_base/code_review/` module with its own SQLite database (`data/code_exercises.db`), a standalone Leitner scheduler, a subprocess-based test runner, and a Textual TUI. Exercises live in `exercises/<slug>/` at the repo root; each has a `problem.md`, a `test_solution.py` (imports from `submission`), and a `solution.py` reference. The `add` subcommand (`uv run code-review add <dir>`) registers an exercise directory in the database.

**Tech Stack:** Python 3.12+, `textual` (already a dep), `sqlite3`/`subprocess`/`difflib` (stdlib), `pytest` (already a dev dep)

---

## File Map

**Create:**
- `src/knowledge_base/code_review/__init__.py` — empty package marker
- `src/knowledge_base/code_review/leitner.py` — 5-box Leitner scheduler; grade→box mapping; due-date computation
- `src/knowledge_base/code_review/db.py` — `code_exercises` and `code_review_log` SQLite tables; CRUD
- `src/knowledge_base/code_review/runner.py` — run pytest against user solution; compute unified diff
- `src/knowledge_base/code_review/cli.py` — `handle_add()` for the `add` subcommand
- `src/knowledge_base/code_review/tui.py` — Textual `App` with exercise list, review flow, grade buttons; `main()`
- `exercises/.gitkeep` — tracks the exercises directory in git
- `tests/code_review/__init__.py`
- `tests/code_review/test_leitner.py`
- `tests/code_review/test_db.py`
- `tests/code_review/test_runner.py`
- `tests/code_review/test_cli.py`

**Modify:**
- `pyproject.toml` — add `code-review` script entry point
- `.gitignore` — add `exercises/**/submission.py`

---

## Exercise Directory Convention

```
exercises/
    quantecon-3-3-geometric-series/
        problem.md          # shown to user; first H1 becomes the title
        solution.py         # reference; revealed after grading (optional)
        test_solution.py    # pytest tests; MUST import from `submission` (not `solution`)
```

`test_solution.py` convention — always import from `submission`:
```python
from submission import geometric_series

def test_base_case():
    assert geometric_series(0.5, 0) == 1.0

def test_known_value():
    assert abs(geometric_series(0.5, 5) - 0.96875) < 1e-9
```

The runner writes the user's solution as `submission.py`, runs pytest with `PYTHONPATH` set to the exercise directory, then deletes `submission.py`.

---

## Task 1: Leitner Scheduler

**Files:**
- Create: `src/knowledge_base/code_review/__init__.py`
- Create: `src/knowledge_base/code_review/leitner.py`
- Create: `tests/code_review/__init__.py`
- Create: `tests/code_review/test_leitner.py`

- [ ] **Step 1: Create the package markers**

```bash
mkdir -p src/knowledge_base/code_review tests/code_review
touch src/knowledge_base/code_review/__init__.py tests/code_review/__init__.py
```

Expected: no output, files created.

- [ ] **Step 2: Write the failing tests**

Create `tests/code_review/test_leitner.py`:

```python
from datetime import datetime, timezone

import pytest

from knowledge_base.code_review.leitner import LeitnerResult, schedule

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_again_resets_to_box_1():
    result = schedule(current_box=3, grade=1, now=NOW)
    assert result.box == 1
    assert result.interval == 1.0


def test_hard_stays_in_current_box():
    result = schedule(current_box=3, grade=2, now=NOW)
    assert result.box == 3
    assert result.interval == 4.0


def test_good_advances_one_box():
    result = schedule(current_box=2, grade=3, now=NOW)
    assert result.box == 3
    assert result.interval == 4.0


def test_easy_advances_two_boxes():
    result = schedule(current_box=2, grade=4, now=NOW)
    assert result.box == 4
    assert result.interval == 8.0


def test_good_caps_at_box_5():
    result = schedule(current_box=5, grade=3, now=NOW)
    assert result.box == 5
    assert result.interval == 16.0


def test_easy_caps_at_box_5():
    result = schedule(current_box=4, grade=4, now=NOW)
    assert result.box == 5
    assert result.interval == 16.0


def test_due_is_iso8601_string():
    result = schedule(current_box=1, grade=3, now=NOW)
    datetime.fromisoformat(result.due)  # should not raise


def test_naive_datetime_is_treated_as_utc():
    naive = datetime(2026, 1, 1)
    result = schedule(current_box=1, grade=3, now=naive)
    assert result.box == 2
```

- [ ] **Step 3: Run tests — expect all to fail**

```bash
uv run pytest tests/code_review/test_leitner.py -v
```

Expected: `ERROR` (module not found) or `FAILED` for all.

- [ ] **Step 4: Implement `leitner.py`**

Create `src/knowledge_base/code_review/leitner.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

INTERVALS: dict[int, int] = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = 5


@dataclass
class LeitnerResult:
    box: int
    interval: float  # days
    due: str         # ISO-8601


def schedule(current_box: int, grade: int, now: datetime) -> LeitnerResult:
    """Map a grade to a new Leitner box and compute next due date.

    grade: 1=Again (box 1), 2=Hard (stay), 3=Good (next), 4=Easy (+2 boxes)
    """
    if grade == 1:
        new_box = 1
    elif grade == 2:
        new_box = current_box
    elif grade == 3:
        new_box = min(current_box + 1, MAX_BOX)
    else:
        new_box = min(current_box + 2, MAX_BOX)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    interval = float(INTERVALS[new_box])
    due = (now + timedelta(days=interval)).isoformat()
    return LeitnerResult(box=new_box, interval=interval, due=due)
```

- [ ] **Step 5: Run tests — expect all to pass**

```bash
uv run pytest tests/code_review/test_leitner.py -v
```

Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/code_review/__init__.py src/knowledge_base/code_review/leitner.py tests/code_review/__init__.py tests/code_review/test_leitner.py
git commit -m "feat(code-review): add Leitner scheduler module"
```

---

## Task 2: DB Layer

**Files:**
- Create: `src/knowledge_base/code_review/db.py`
- Create: `tests/code_review/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/code_review/test_db.py`:

```python
from datetime import datetime, timezone

import pytest

from knowledge_base.code_review.db import (
    add_exercise,
    get_due_exercises,
    get_exercise_by_slug,
    init_db,
    insert_review_log,
    update_exercise_scheduling,
)


@pytest.fixture
def conn(tmp_path):
    return init_db(tmp_path / "test.db")


def test_init_db_creates_tables(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "code_exercises" in tables
    assert "code_review_log" in tables


def test_add_exercise_returns_id(conn):
    eid = add_exercise(conn, "my-slug", "My Title", "quantecon")
    assert isinstance(eid, int)
    assert eid > 0


def test_get_exercise_by_slug(conn):
    add_exercise(conn, "slug-a", "Title A")
    ex = get_exercise_by_slug(conn, "slug-a")
    assert ex is not None
    assert ex["title"] == "Title A"
    assert ex["box"] == 1
    assert ex["reps"] == 0


def test_get_exercise_by_slug_missing_returns_none(conn):
    assert get_exercise_by_slug(conn, "no-such-slug") is None


def test_get_due_exercises_includes_null_due(conn):
    add_exercise(conn, "new-exercise", "New")
    now = datetime.now(timezone.utc).isoformat()
    due = get_due_exercises(conn, now)
    assert any(e["slug"] == "new-exercise" for e in due)


def test_get_due_exercises_excludes_future(conn):
    eid = add_exercise(conn, "future-ex", "Future")
    update_exercise_scheduling(conn, eid, box=3, due="2099-01-01T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    as_of = "2026-06-01T00:00:00+00:00"
    due = get_due_exercises(conn, as_of)
    assert not any(e["slug"] == "future-ex" for e in due)


def test_update_exercise_scheduling_increments_reps(conn):
    eid = add_exercise(conn, "rep-test", "Rep Test")
    update_exercise_scheduling(conn, eid, box=2, due="2026-01-03T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    ex = get_exercise_by_slug(conn, "rep-test")
    assert ex["reps"] == 1
    assert ex["box"] == 2


def test_insert_review_log(conn):
    eid = add_exercise(conn, "log-test", "Log Test")
    review_id = insert_review_log(conn, {
        "exercise_id": eid,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "grade": 3,
        "prior_box": 1,
        "new_box": 2,
        "elapsed_days": 0.0,
    })
    assert review_id > 0
```

- [ ] **Step 2: Run tests — expect all to fail**

```bash
uv run pytest tests/code_review/test_db.py -v
```

Expected: `ERROR` (module not found).

- [ ] **Step 3: Implement `db.py`**

Create `src/knowledge_base/code_review/db.py`:

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[3]
DB_PATH = _REPO_ROOT / "data" / "code_exercises.db"

_DDL_EXERCISES = """
CREATE TABLE IF NOT EXISTS code_exercises (
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

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS code_review_log (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id  INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
    timestamp    TEXT    NOT NULL,
    grade        INTEGER NOT NULL,
    prior_box    INTEGER NOT NULL,
    new_box      INTEGER NOT NULL,
    elapsed_days REAL    NOT NULL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_code_exercises_due  ON code_exercises (due);
CREATE INDEX IF NOT EXISTS idx_code_review_log_eid ON code_review_log (exercise_id);
"""


def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
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
    return conn


def add_exercise(
    conn: sqlite3.Connection, slug: str, title: str, source: str = ""
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO code_exercises (slug, title, source, added) VALUES (?, ?, ?, ?)",
        (slug, title, source, now),
    )
    conn.commit()
    return cur.lastrowid


def get_exercise_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM code_exercises WHERE slug = ?", (slug,)
    ).fetchone()
    return dict(row) if row else None


def get_due_exercises(conn: sqlite3.Connection, as_of: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM code_exercises WHERE due IS NULL OR due <= ? ORDER BY due ASC NULLS FIRST",
        (as_of,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_exercise_scheduling(
    conn: sqlite3.Connection, exercise_id: int, box: int, due: str, now: str
) -> None:
    conn.execute(
        "UPDATE code_exercises SET box=?, due=?, last_review=?, reps=reps+1 WHERE exercise_id=?",
        (box, due, now, exercise_id),
    )
    conn.commit()


def insert_review_log(conn: sqlite3.Connection, review: dict) -> int:
    cols = list(review.keys())
    cur = conn.execute(
        f"INSERT INTO code_review_log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [review[c] for c in cols],
    )
    conn.commit()
    return cur.lastrowid
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
uv run pytest tests/code_review/test_db.py -v
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/db.py tests/code_review/test_db.py
git commit -m "feat(code-review): add SQLite DB layer for code exercises"
```

---

## Task 3: Test Runner + Diff

**Files:**
- Create: `src/knowledge_base/code_review/runner.py`
- Create: `tests/code_review/test_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/code_review/test_runner.py`:

```python
from pathlib import Path

import pytest

from knowledge_base.code_review.runner import compute_diff, run_tests


def _make_exercise(tmp_path: Path, test_code: str) -> Path:
    ex_dir = tmp_path / "ex"
    ex_dir.mkdir()
    (ex_dir / "test_solution.py").write_text(test_code)
    return ex_dir


def test_run_tests_passing(tmp_path):
    ex_dir = _make_exercise(
        tmp_path,
        "from submission import add\ndef test_add(): assert add(1, 2) == 3\n",
    )
    passed, output = run_tests(ex_dir, "def add(a, b): return a + b\n")
    assert passed
    assert "1 passed" in output


def test_run_tests_failing(tmp_path):
    ex_dir = _make_exercise(
        tmp_path,
        "from submission import add\ndef test_add(): assert add(1, 2) == 3\n",
    )
    passed, output = run_tests(ex_dir, "def add(a, b): return a - b\n")
    assert not passed
    assert "FAILED" in output or "AssertionError" in output


def test_run_tests_removes_submission(tmp_path):
    ex_dir = _make_exercise(
        tmp_path,
        "from submission import f\ndef test_f(): assert f() == 1\n",
    )
    run_tests(ex_dir, "def f(): return 1\n")
    assert not (ex_dir / "submission.py").exists()


def test_run_tests_removes_submission_even_on_failure(tmp_path):
    ex_dir = _make_exercise(
        tmp_path,
        "from submission import f\ndef test_f(): assert f() == 1\n",
    )
    run_tests(ex_dir, "def f(): return 999\n")
    assert not (ex_dir / "submission.py").exists()


def test_compute_diff_empty_when_no_solution(tmp_path):
    diff = compute_diff("x = 1\n", tmp_path / "solution.py")
    assert diff == ""


def test_compute_diff_identical_is_empty(tmp_path):
    sol = tmp_path / "solution.py"
    sol.write_text("def f(): return 1\n")
    diff = compute_diff("def f(): return 1\n", sol)
    assert diff == ""


def test_compute_diff_shows_changed_lines(tmp_path):
    sol = tmp_path / "solution.py"
    sol.write_text("def add(a, b):\n    return a + b\n")
    diff = compute_diff("def add(a, b):\n    return a - b\n", sol)
    assert "-    return a - b" in diff
    assert "+    return a + b" in diff
```

- [ ] **Step 2: Run tests — expect all to fail**

```bash
uv run pytest tests/code_review/test_runner.py -v
```

Expected: `ERROR` (module not found).

- [ ] **Step 3: Implement `runner.py`**

Create `src/knowledge_base/code_review/runner.py`:

```python
import difflib
import os
import subprocess
from pathlib import Path


def run_tests(exercise_dir: Path, user_code: str) -> tuple[bool, str]:
    """Write user_code as submission.py, run pytest, return (passed, output).

    submission.py is always deleted after the run, even on error.
    Tests must import from `submission` (not `solution`).
    """
    submission = exercise_dir / "submission.py"
    try:
        submission.write_text(user_code)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(exercise_dir)
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                str(exercise_dir / "test_solution.py"),
                "-v", "--tb=short", "--no-header", "-p", "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        output = result.stdout + (result.stderr if result.stderr else "")
        return result.returncode == 0, output
    finally:
        if submission.exists():
            submission.unlink()


def compute_diff(user_code: str, solution_path: Path) -> str:
    """Return a unified diff between user_code and the reference solution.

    Returns empty string if solution.py does not exist or files are identical.
    """
    if not solution_path.exists():
        return ""
    reference = solution_path.read_text()
    lines = list(
        difflib.unified_diff(
            user_code.splitlines(keepends=True),
            reference.splitlines(keepends=True),
            fromfile="your solution",
            tofile="reference solution",
        )
    )
    return "".join(lines)
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
uv run pytest tests/code_review/test_runner.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/runner.py tests/code_review/test_runner.py
git commit -m "feat(code-review): add test runner and diff computation"
```

---

## Task 4: Add CLI

**Files:**
- Create: `src/knowledge_base/code_review/cli.py`
- Create: `tests/code_review/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/code_review/test_cli.py`:

```python
import sys
from pathlib import Path

import pytest

from knowledge_base.code_review.cli import handle_add
from knowledge_base.code_review.db import get_exercise_by_slug, init_db


@pytest.fixture
def ex_dir(tmp_path):
    d = tmp_path / "quantecon-3-3-fibonacci"
    d.mkdir()
    (d / "problem.md").write_text("# Fibonacci Sequence\nImplement `fibonacci(n)`.\n")
    (d / "test_solution.py").write_text(
        "from submission import fibonacci\n"
        "def test_base(): assert fibonacci(0) == 0\n"
        "def test_known(): assert fibonacci(10) == 55\n"
    )
    return d


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_handle_add_registers_exercise(ex_dir, db_path):
    handle_add([str(ex_dir)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "quantecon-3-3-fibonacci")
    assert ex is not None
    assert ex["title"] == "Fibonacci Sequence"
    assert ex["box"] == 1


def test_handle_add_extracts_title_from_h1(ex_dir, db_path):
    handle_add([str(ex_dir)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "quantecon-3-3-fibonacci")
    assert ex["title"] == "Fibonacci Sequence"


def test_handle_add_with_source(ex_dir, db_path):
    handle_add([str(ex_dir), "--source", "quantecon-python"], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "quantecon-3-3-fibonacci")
    assert ex["source"] == "quantecon-python"


def test_handle_add_fails_on_missing_problem_md(tmp_path, db_path):
    d = tmp_path / "incomplete-exercise"
    d.mkdir()
    (d / "test_solution.py").write_text("# tests\n")
    with pytest.raises(SystemExit):
        handle_add([str(d)], db_path=db_path)


def test_handle_add_fails_on_missing_test_file(tmp_path, db_path):
    d = tmp_path / "incomplete-exercise"
    d.mkdir()
    (d / "problem.md").write_text("# Title\n")
    with pytest.raises(SystemExit):
        handle_add([str(d)], db_path=db_path)


def test_handle_add_fails_on_duplicate_slug(ex_dir, db_path):
    handle_add([str(ex_dir)], db_path=db_path)
    with pytest.raises(SystemExit):
        handle_add([str(ex_dir)], db_path=db_path)


def test_handle_add_falls_back_to_dirname_when_no_h1(tmp_path, db_path):
    d = tmp_path / "no-heading-exercise"
    d.mkdir()
    (d / "problem.md").write_text("No heading here.\n")
    (d / "test_solution.py").write_text("def test_pass(): pass\n")
    handle_add([str(d)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "no-heading-exercise")
    assert ex["title"] == "no-heading-exercise"
```

- [ ] **Step 2: Run tests — expect all to fail**

```bash
uv run pytest tests/code_review/test_cli.py -v
```

Expected: `ERROR` (module not found).

- [ ] **Step 3: Implement `cli.py`**

Create `src/knowledge_base/code_review/cli.py`:

```python
import argparse
import sys
from pathlib import Path

from knowledge_base.code_review.db import DB_PATH, add_exercise, get_exercise_by_slug, init_db


def _extract_title(problem_md: Path) -> str:
    for line in problem_md.read_text().splitlines():
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

    exercise_id = add_exercise(conn, slug, title, parsed.source)
    print(f"Added '{slug}' — {title} (id={exercise_id})")
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
uv run pytest tests/code_review/test_cli.py -v
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/cli.py tests/code_review/test_cli.py
git commit -m "feat(code-review): add exercise registration CLI"
```

---

## Task 5: TUI Review Loop

**Files:**
- Create: `src/knowledge_base/code_review/tui.py`

No unit tests for the Textual TUI — verify manually with a smoke test at the end of this task.

- [ ] **Step 1: Create `tui.py`**

Create `src/knowledge_base/code_review/tui.py`:

```python
"""Textual TUI for code-review spaced practice.

Flow per session:
  ExerciseListScreen  →  (select one)
  ReviewScreen        →  problem display → $EDITOR → test results + diff → grade buttons
  → back to ExerciseListScreen
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from knowledge_base.code_review.cli import handle_add
from knowledge_base.code_review.db import (
    DB_PATH,
    get_due_exercises,
    init_db,
    insert_review_log,
    update_exercise_scheduling,
)
from knowledge_base.code_review.leitner import schedule as leitner_schedule
from knowledge_base.code_review.runner import compute_diff, run_tests

_REPO_ROOT = Path(__file__).parents[3]
EXERCISES_DIR = _REPO_ROOT / "exercises"


# ---------------------------------------------------------------------------
# Exercise list screen
# ---------------------------------------------------------------------------

class ExerciseListScreen(Screen):
    BINDINGS = [Binding("q", "app.quit", "Quit")]

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self._conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(id="exercise-list")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()

    def _reload(self) -> None:
        lv = self.query_one("#exercise-list", ListView)
        lv.clear()
        now = datetime.now(timezone.utc).isoformat()
        exercises = get_due_exercises(self._conn, now)
        if not exercises:
            lv.append(ListItem(Label("No exercises due. Run: uv run code-review add <dir>")))
        else:
            for ex in exercises:
                due_str = ex["due"][:10] if ex["due"] else "new"
                label = f"[{due_str}]  {ex['slug']}  —  {ex['title']}  (box {ex['box']}, reps {ex['reps']})"
                item = ListItem(Label(label))
                item._exercise = ex  # type: ignore[attr-defined]
                lv.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not hasattr(item, "_exercise"):
            return
        self.app.push_screen(ReviewScreen(item._exercise, self._conn))

    def on_screen_resume(self) -> None:
        self._reload()


# ---------------------------------------------------------------------------
# Review screen
# ---------------------------------------------------------------------------

class ReviewScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    CSS = """
    #problem { margin: 1 2; }
    #results { margin: 1 2; }
    #diff    { margin: 1 2; color: $text-muted; }
    #grade-row { height: 3; margin: 1 2; }
    #grade-row Button { margin: 0 1; }
    .hidden { display: none; }
    """

    def __init__(self, exercise: dict, conn, **kwargs):
        super().__init__(**kwargs)
        self._exercise = exercise
        self._conn = conn
        self._user_code = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(id="problem"),
            Static(id="results", classes="hidden"),
            Static(id="diff", classes="hidden"),
            Horizontal(
                Button("Again (1)", id="grade-1", variant="error"),
                Button("Hard  (2)", id="grade-2", variant="warning"),
                Button("Good  (3)", id="grade-3", variant="success"),
                Button("Easy  (4)", id="grade-4", variant="primary"),
                id="grade-row",
                classes="hidden",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        exercise_dir = EXERCISES_DIR / self._exercise["slug"]
        problem_md = exercise_dir / "problem.md"
        text = problem_md.read_text() if problem_md.exists() else f"[red]Missing: {problem_md}[/red]"
        self.query_one("#problem", Static).update(text)
        self.set_timer(0.1, self._open_editor)

    async def _open_editor(self) -> None:
        editor = os.environ.get("EDITOR", "vi")
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            tmpfile = Path(f.name)

        async with self.app.suspend():
            subprocess.run([editor, str(tmpfile)])

        self._user_code = tmpfile.read_text()
        tmpfile.unlink(missing_ok=True)

        exercise_dir = EXERCISES_DIR / self._exercise["slug"]
        passed, output = run_tests(exercise_dir, self._user_code)
        diff = compute_diff(self._user_code, exercise_dir / "solution.py")

        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        self.query_one("#results", Static).update(f"{status}\n\n{output}")
        self.query_one("#results").remove_class("hidden")

        if diff:
            self.query_one("#diff", Static).update(f"[bold]Diff vs. reference:[/bold]\n{diff}")
            self.query_one("#diff").remove_class("hidden")

        self.query_one("#grade-row").remove_class("hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        grade = int(event.button.id.split("-")[1])  # "grade-1" → 1
        now = datetime.now(timezone.utc)
        ex = self._exercise

        last_review = ex.get("last_review")
        if last_review:
            lr = datetime.fromisoformat(last_review)
            if lr.tzinfo is None:
                lr = lr.replace(tzinfo=timezone.utc)
            elapsed_days = (now - lr).total_seconds() / 86400.0
        else:
            elapsed_days = 0.0

        result = leitner_schedule(ex["box"], grade, now)
        update_exercise_scheduling(self._conn, ex["exercise_id"], result.box, result.due, now.isoformat())
        insert_review_log(self._conn, {
            "exercise_id": ex["exercise_id"],
            "timestamp": now.isoformat(),
            "grade": grade,
            "prior_box": ex["box"],
            "new_box": result.box,
            "elapsed_days": elapsed_days,
        })
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# App + entry point
# ---------------------------------------------------------------------------

class CodeReviewApp(App):
    def on_mount(self) -> None:
        conn = init_db(DB_PATH)
        self.push_screen(ExerciseListScreen(conn))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "add":
        handle_add(sys.argv[2:])
    else:
        CodeReviewApp().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify imports parse without error**

```bash
uv run python -c "from knowledge_base.code_review.tui import CodeReviewApp; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Create exercises directory and gitkeep**

```bash
mkdir -p exercises
touch exercises/.gitkeep
```

- [ ] **Step 4: Manual smoke test — add a fixture exercise and launch the TUI**

Create a minimal exercise to smoke-test the full loop:

```bash
mkdir -p exercises/smoke-test
```

Create `exercises/smoke-test/problem.md`:
```markdown
# Smoke Test

Implement `double(x)` that returns `x * 2`.
```

Create `exercises/smoke-test/test_solution.py`:
```python
from submission import double

def test_double():
    assert double(3) == 6

def test_double_negative():
    assert double(-1) == -2
```

Create `exercises/smoke-test/solution.py`:
```python
def double(x):
    return x * 2
```

Register and launch:
```bash
uv run code-review add exercises/smoke-test/
uv run code-review
```

Expected walk-through:
1. TUI opens showing "smoke-test — Smoke Test (box 1, reps 0)"
2. Select it — problem statement displays, `$EDITOR` opens
3. Type `def double(x): return x * 2`, save and quit
4. Tests show `2 passed`; diff view is empty (identical to reference)
5. Press "Good (3)" — returns to list; smoke-test now has due date set

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/code_review/tui.py exercises/.gitkeep exercises/smoke-test/
git commit -m "feat(code-review): add Textual TUI review loop"
```

---

## Task 6: Wire Up Entry Point + Gitignore

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Add entry point to `pyproject.toml`**

In `pyproject.toml`, change:

```toml
[project.scripts]
review-gen = "knowledge_base.srs.generation_tui:main"
gen-import = "knowledge_base.srs.generation_import:main"
gen-import-md = "knowledge_base.srs.md_importer:main"
gen-import-csv = "knowledge_base.srs.csv_importer:main"
```

to:

```toml
[project.scripts]
review-gen = "knowledge_base.srs.generation_tui:main"
gen-import = "knowledge_base.srs.generation_import:main"
gen-import-md = "knowledge_base.srs.md_importer:main"
gen-import-csv = "knowledge_base.srs.csv_importer:main"
code-review = "knowledge_base.code_review.tui:main"
```

- [ ] **Step 2: Sync to register the new entry point**

```bash
uv sync
```

Expected: `Resolved ... packages` with no errors.

- [ ] **Step 3: Add submission files to .gitignore**

Append to `.gitignore`:

```
# code-review: user submissions written during test runs
exercises/**/submission.py
```

- [ ] **Step 4: Verify entry point works**

```bash
uv run code-review --help
```

Expected: Textual app launches (or `--help` exits cleanly — Textual may not have a --help flag, so the app just opens; `Ctrl-C` to exit is fine).

```bash
uv run code-review add --help
```

Expected: argparse help text showing `usage: code-review add [-h] [--source SOURCE] exercise_dir`.

- [ ] **Step 5: Run the full test suite to confirm nothing is broken**

```bash
uv run pytest -v
```

Expected: all existing tests plus the new `code_review/` tests pass. Watch for any import-time side effects.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "feat(code-review): register entry point and gitignore submission files"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| Separate `uv run code-review` entry point | Task 6 |
| Leitner scheduling | Task 1 |
| SQLite persistence (exercises + review log) | Task 2 |
| `$EDITOR` for writing solution | Task 5 (`_open_editor`) |
| pytest runner against user's solution | Task 3 |
| Side-by-side diff vs. reference | Task 3 + Task 5 |
| Again/Hard/Good/Easy grade buttons | Task 5 |
| `code-review add <dir>` to register exercises | Task 4 + Task 6 |
| `exercises/**/submission.py` gitignored | Task 6 |
| Tests import from `submission` (not `solution`) | Convention documented above Task 1 |

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency check:**
- `leitner.schedule()` returns `LeitnerResult` with `.box`, `.interval`, `.due` — used correctly in `tui.py`
- `db.add_exercise()` returns `int` (exercise_id) — used correctly in `cli.py`
- `db.get_due_exercises()` returns `list[dict]` — iterated correctly in `ExerciseListScreen._reload()`
- `runner.run_tests()` returns `tuple[bool, str]` — destructured correctly in `ReviewScreen._open_editor()`
- `runner.compute_diff()` returns `str` — checked for truthiness correctly before display
- `db.update_exercise_scheduling()` takes `(conn, exercise_id, box, due, now)` — called with correct positional args in `ReviewScreen.on_button_pressed()`

---

## Usage After Implementation

```bash
# Add an exercise (create the directory with problem.md + test_solution.py first)
uv run code-review add exercises/quantecon-3-3-geometric-series/

# Review due exercises
uv run code-review
```
