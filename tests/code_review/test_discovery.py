from pathlib import Path

import pytest

from knowledge_base.code_review.db import (
    add_exercise,
    discover_exercises,
    get_exercise_by_slug,
    init_db,
    sync_exercises_from_disk,
)


def _make_exercise(d: Path, *, problem: bool = True, tests: bool = True, solution: bool = True):
    d.mkdir(parents=True, exist_ok=True)
    if problem:
        (d / "problem.md").write_text("# Title for " + d.name + "\nbody\n")
    if tests:
        (d / "test_solution.py").write_text("def test_pass(): pass\n")
    if solution:
        (d / "solution.py").write_text("def fn(): pass\n")


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_discover_finds_complete_dirs(tmp_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "ex-a")
    _make_exercise(root / "ex-b")
    found = discover_exercises(root)
    slugs = [t[0] for t in found]
    assert slugs == ["ex-a", "ex-b"]


def test_discover_skips_dirs_missing_any_of_trio(tmp_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "complete")
    _make_exercise(root / "no-problem", problem=False)
    _make_exercise(root / "no-tests", tests=False)
    _make_exercise(root / "no-solution", solution=False)
    found = {t[0] for t in discover_exercises(root)}
    assert found == {"complete"}


def test_discover_walks_nested_dirs(tmp_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "quantecon" / "python-programming" / "quantecon-3-1")
    found = discover_exercises(root)
    assert len(found) == 1
    slug, title, rel_path = found[0]
    assert slug == "quantecon-3-1"
    assert rel_path == "quantecon/python-programming/quantecon-3-1"


def test_discover_extracts_title_from_h1(tmp_path):
    root = tmp_path / "exercises"
    d = root / "ex"
    _make_exercise(d)
    (d / "problem.md").write_text("# Fibonacci Sequence\nImplement it.\n")
    found = discover_exercises(root)
    assert found[0][1] == "Fibonacci Sequence"


def test_discover_falls_back_to_dirname_when_no_h1(tmp_path):
    root = tmp_path / "exercises"
    d = root / "no-heading"
    _make_exercise(d)
    (d / "problem.md").write_text("body without heading\n")
    found = discover_exercises(root)
    assert found[0][1] == "no-heading"


def test_discover_returns_empty_for_missing_root(tmp_path):
    assert discover_exercises(tmp_path / "does-not-exist") == []


def test_sync_registers_new_exercises(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "ex-a")
    _make_exercise(root / "ex-b")
    conn = init_db(db_path)
    added = sync_exercises_from_disk(conn, root)
    assert sorted(added) == ["ex-a", "ex-b"]
    assert get_exercise_by_slug(conn, "ex-a") is not None
    assert get_exercise_by_slug(conn, "ex-b") is not None


def test_sync_is_idempotent(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "ex-a")
    conn = init_db(db_path)
    sync_exercises_from_disk(conn, root)
    added_again = sync_exercises_from_disk(conn, root)
    assert added_again == []


def test_sync_preserves_existing_scheduling_state(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "ex-a")
    conn = init_db(db_path)
    eid = add_exercise(conn, "ex-a", "Manual Title", path="ex-a")
    conn.execute(
        "UPDATE code_exercises SET phase=2, reps=7, due='2099-01-01T00:00:00+00:00' "
        "WHERE exercise_id=?",
        (eid,),
    )
    conn.commit()
    added = sync_exercises_from_disk(conn, root)
    assert added == []
    ex = get_exercise_by_slug(conn, "ex-a")
    assert ex["phase"] == 2
    assert ex["reps"] == 7
    assert ex["title"] == "Manual Title"


def test_sync_picks_up_newly_added_dir(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "ex-a")
    conn = init_db(db_path)
    sync_exercises_from_disk(conn, root)
    _make_exercise(root / "ex-b")
    added = sync_exercises_from_disk(conn, root)
    assert added == ["ex-b"]


def test_sync_skips_dirs_missing_solution_py(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "complete")
    _make_exercise(root / "no-solution", solution=False)
    conn = init_db(db_path)
    added = sync_exercises_from_disk(conn, root)
    assert added == ["complete"]
    assert get_exercise_by_slug(conn, "no-solution") is None


def test_sync_handles_slug_collision_first_wins(tmp_path, db_path):
    root = tmp_path / "exercises"
    _make_exercise(root / "alpha" / "shared-slug")
    _make_exercise(root / "beta" / "shared-slug")
    conn = init_db(db_path)
    added = sync_exercises_from_disk(conn, root)
    assert added == ["shared-slug"]
    ex = get_exercise_by_slug(conn, "shared-slug")
    assert ex["path"] == "alpha/shared-slug"
