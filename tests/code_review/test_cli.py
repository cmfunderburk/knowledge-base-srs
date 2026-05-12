import sys
from pathlib import Path

import pytest

from knowledge_base.code_review.cli import handle_add
from knowledge_base.code_review.db import get_exercise_by_slug, init_db


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


def test_handle_add_fails_on_missing_test_file(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    d = exercises_root / "incomplete-exercise"
    d.mkdir(parents=True)
    (d / "problem.md").write_text("# Title\n")
    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)
    with pytest.raises(SystemExit) as exc_info:
        handle_add([str(d)], db_path=db_path)
    assert exc_info.value.code == 1


def test_handle_add_fails_on_duplicate_slug(ex_dir, db_path):
    handle_add([str(ex_dir)], db_path=db_path)
    with pytest.raises(SystemExit) as exc_info:
        handle_add([str(ex_dir)], db_path=db_path)
    assert exc_info.value.code == 1


def test_handle_add_falls_back_to_dirname_when_no_h1(tmp_path, db_path, monkeypatch):
    from knowledge_base.code_review import db as db_mod
    from knowledge_base.code_review import cli as cli_mod
    exercises_root = tmp_path / "exercises"
    d = exercises_root / "no-heading-exercise"
    d.mkdir(parents=True)
    (d / "problem.md").write_text("No heading here.\n")
    (d / "test_solution.py").write_text("def test_pass(): pass\n")
    monkeypatch.setattr(db_mod, "EXERCISES_DIR", exercises_root)
    monkeypatch.setattr(cli_mod, "EXERCISES_DIR", exercises_root)
    handle_add([str(d)], db_path=db_path)
    conn = init_db(db_path)
    ex = get_exercise_by_slug(conn, "no-heading-exercise")
    assert ex["title"] == "no-heading-exercise"


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
