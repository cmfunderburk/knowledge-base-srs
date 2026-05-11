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
