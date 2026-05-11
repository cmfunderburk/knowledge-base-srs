import difflib
import os
import subprocess
import sys
from pathlib import Path


def _test_python() -> str:
    """Python interpreter used to run exercise tests.

    Set CODE_REVIEW_PYTHON to override — e.g. point at a conda environment:
        export CODE_REVIEW_PYTHON=$(conda run -n base which python)
    Defaults to the current interpreter (sys.executable).
    """
    return os.environ.get("CODE_REVIEW_PYTHON", sys.executable)


def run_tests(exercise_dir: Path, user_code: str) -> tuple[bool, str]:
    """Write user_code as submission.py, run pytest, return (passed, output).

    submission.py is always deleted after the run, even on error.
    Tests must import from `submission` (not `solution`).
    """
    submission = exercise_dir / "submission.py"
    try:
        submission.write_text(user_code)
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{exercise_dir}:{existing}" if existing else str(exercise_dir)
        env.setdefault("MPLBACKEND", "Agg")  # prevent Qt display errors in headless test runs
        try:
            result = subprocess.run(
                [
                    _test_python(), "-m", "pytest",
                    str(exercise_dir / "test_solution.py"),
                    "-v", "--tb=short", "--no-header", "-p", "no:cacheprovider",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "Test run timed out after 30 seconds."
    finally:
        if submission.exists():
            submission.unlink()


def compute_side_by_side_diff(
    user_code: str, solution_path: Path
) -> tuple[str, str] | None:
    """Return (left_markup, right_markup) for side-by-side diff display.

    Left = your solution (deletions in red), right = reference (insertions in green).
    Returns None if solution.py does not exist or files are identical.
    Uses Rich markup — escape [ ] in content before wrapping in color tags.
    """
    if not solution_path.exists():
        return None
    reference = solution_path.read_text()
    if user_code == reference:
        return None

    def esc(s: str) -> str:
        return s.replace("[", r"\[")

    left_lines = user_code.splitlines()
    right_lines = reference.splitlines()
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)

    left_out: list[str] = []
    right_out: list[str] = []
    has_diff = False

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in left_lines[i1:i2]:
                left_out.append(esc(line))
                right_out.append(esc(line))
        elif tag == "replace":
            has_diff = True
            lb, rb = left_lines[i1:i2], right_lines[j1:j2]
            for k in range(max(len(lb), len(rb))):
                left_out.append(f"[red]{esc(lb[k])}[/red]" if k < len(lb) else "")
                right_out.append(f"[green]{esc(rb[k])}[/green]" if k < len(rb) else "")
        elif tag == "delete":
            has_diff = True
            for line in left_lines[i1:i2]:
                left_out.append(f"[red]{esc(line)}[/red]")
                right_out.append("")
        elif tag == "insert":
            has_diff = True
            for line in right_lines[j1:j2]:
                left_out.append("")
                right_out.append(f"[green]{esc(line)}[/green]")

    if not has_diff:
        return None
    return "\n".join(left_out), "\n".join(right_out)


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
