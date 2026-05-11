import argparse
import sqlite3
import sys
from pathlib import Path

from knowledge_base.code_review.db import DB_PATH, add_exercise, get_exercise_by_slug, init_db


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
        exercise_id = add_exercise(conn, slug, title, parsed.source)
    except sqlite3.IntegrityError:
        print(f"error: exercise '{slug}' is already registered", file=sys.stderr)
        sys.exit(1)
    print(f"Added '{slug}' — {title} (id={exercise_id})")
