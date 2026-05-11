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
