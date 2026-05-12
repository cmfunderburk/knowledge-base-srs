# Nested Exercise Directories — Design

## Context

`code-review` was built assuming a flat `exercises/<slug>/` layout. The exercises directory has been reorganized to support multiple sources and courses:

```
exercises/
    quantecon/
        python-programming/
            quantecon-3-1/
            quantecon-4-2/
            ...
        intro/                  # placeholder
        intermediate/           # placeholder
        advanced/               # placeholder
        datascience/            # placeholder
        continuous-markov-chains/  # placeholder
    smoke-test/                 # not an exercise; build-time fixture
```

Slugs (e.g. `quantecon-3-1`) remain globally unique, but exercises now live at varying depths. Two runtime call sites in `tui.py` resolve the directory as `EXERCISES_DIR / slug`, which fails for any nested exercise. The DB has no path information beyond slug.

## Goals

1. Make `code-review` work with arbitrarily nested exercise directories under `exercises/`.
2. Surface the directory taxonomy in the TUI where it adds value (selection and stats screens).
3. Relocate `smoke-test/` out of `exercises/` since it's a test fixture, not an exercise.

## Non-goals

- Auto-discovering exercises from disk. Registration via `code-review add <dir>` stays explicit.
- Hierarchical grouping in the due-queue (kept ordered by due date).
- Changing the Leitner scheduling, grading flow, or test runner contract.
- Renaming or reworking the `source` column (it stays as a free-text label, independent of `path`).

## Design

### Schema

Add a `path` column to `code_exercises`:

```sql
path TEXT NOT NULL  -- path relative to exercises/, e.g. "quantecon/python-programming/quantecon-3-1"
```

`slug` remains the natural key (UNIQUE). `path` is informational/resolution metadata. Storing the relative path (rather than absolute) keeps the DB portable across machines.

### Migration

`init_db` detects whether `path` exists via `PRAGMA table_info(code_exercises)`. If absent:

1. `ALTER TABLE code_exercises ADD COLUMN path TEXT NOT NULL DEFAULT '';`
2. Collect `slug` values where `path = ''` (these are pre-migration rows whose directory location is unknown).
3. Delete those rows.
4. `init_db` returns the connection as before, but the list of purged slugs is exposed via a module-level `LAST_MIGRATION_PURGE: list[str]` set on each call. Both `cli.handle_add` and `tui.CodeReviewApp.on_mount` check this list after `init_db` and surface it — `handle_add` via `print(..., file=sys.stderr)`, the TUI via `self.notify(...)` once the screen is mounted.

This is acceptable because the only pre-migration row in the live DB references the already-deleted `quantecon-3-6-1` exercise. Documenting the loud-removal behavior makes the migration safe even if other DBs exist.

### CLI (`cli.py`)

`handle_add` computes the relative path:

```python
exercise_dir = Path(parsed.exercise_dir).resolve()
try:
    rel_path = exercise_dir.relative_to(EXERCISES_DIR.resolve())
except ValueError:
    print(f"error: {exercise_dir} is not inside {EXERCISES_DIR}", file=sys.stderr)
    sys.exit(1)
slug = exercise_dir.name
```

Both `slug` and `str(rel_path)` are passed to `add_exercise`. `EXERCISES_DIR` moves from `tui.py` into `db.py` alongside `DB_PATH` (both are repo-relative constants); `tui.py` and `cli.py` both import it from there.

`add_exercise(conn, slug, title, source, path)` signature gains a required `path` parameter.

### Runtime resolution (`tui.py`)

At `tui.py:364` and `tui.py:399`, replace:

```python
exercise_dir = EXERCISES_DIR / self._exercise["slug"]
```

with:

```python
exercise_dir = EXERCISES_DIR / self._exercise["path"]
```

No other resolution paths exist.

### TUI grouping

#### `MassedBrowseScreen` and `StatsScreen`

Group exercises by **category** = the path with the final slug segment stripped. Examples:

| `path`                                          | category                          |
| ----------------------------------------------- | --------------------------------- |
| `quantecon/python-programming/quantecon-3-1`    | `quantecon/python-programming`    |
| `quantecon/intermediate/foo`                    | `quantecon/intermediate`          |
| `smoke-test` (won't exist after cleanup, but…)  | `(root)`                          |

Render order:
- Categories sorted alphabetically; `(root)` (if any) first.
- Exercises within a category sorted by slug.

Implementation: insert a non-selectable header `ListItem` (no `_exercise` attribute, dimmed style) before each category group. The existing `space`/`enter` handling in `MassedBrowseScreen.on_key` already ignores items without `_exercise`, so headers are naturally skipped.

#### `ExerciseListScreen` (due queue)

Keep due-date ordering. Extend the label to include the category prefix for context:

```
[2026-05-12]  quantecon/python-programming · quantecon-3-1 — Title  (box 2, reps 3)
```

For root-level exercises, omit the prefix (`slug — title`).

### `smoke-test` relocation

- Move `exercises/smoke-test/` → `tests/code_review/fixtures/smoke-test/`.
- No live code references it — only historical plan docs under `docs/superpowers/plans/`, which are archival.
- Update `exercises/.gitignore` (or root) if it specifically references `smoke-test` (verified during implementation).

### Tests

- `test_db.py`:
  - Add `test_init_db_migrates_path_column`: create a connection against a pre-migration schema (no `path` column), insert a row, call `init_db` again, assert `path` column exists and the no-path row was removed (with stderr notice).
  - Update existing `add_exercise` tests to pass `path`.
- `test_cli.py`:
  - Update fixtures to place the exercise inside an `exercises/` temp root and assert the stored `path` matches the relative path (both flat and nested cases).
  - Add `test_handle_add_rejects_dir_outside_exercises_root`.
- New `tests/code_review/test_tui_grouping.py` (lightweight, no Textual app):
  - Unit-test a helper `group_by_category(exercises)` that returns the ordered (category, [exercises]) sequence used by `MassedBrowseScreen` and `StatsScreen`.
- Test fixture move: any test importing or referencing `exercises/smoke-test` updates to `tests/code_review/fixtures/smoke-test`. (Grep confirmed no current references in `src/` or `tests/`.)

## Risks and mitigations

- **Migration on populated DB**: Mitigated by purging only no-path rows and printing a loud notice. The live DB has one stale row; user-confirmed acceptable to drop.
- **Path drift after move**: Exercises moved on disk without re-registering will resolve to a missing directory. The runtime already handles missing `problem.md` (`tui.py:369`) with a visible error. We don't add automatic discovery — user re-runs `code-review add` if they restructure.
- **Slug collision across subtrees**: Slug stays globally unique (DB constraint enforces it), so collisions surface at registration time rather than as silent ambiguity.

## Out of scope

- A `code-review move` or `code-review rescan` command (consider later if reshuffling becomes frequent).
- Multi-level grouping UI (e.g., expandable category trees in the browser screen).
- Backfilling `path` for unknown pre-migration rows by walking the tree.
