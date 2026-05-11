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
