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
