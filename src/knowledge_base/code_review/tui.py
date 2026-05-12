"""Textual TUI for code-review spaced practice.

Screens:
  ExerciseListScreen   — SRS queue (due exercises); m=massed, s=stats
  MassedBrowseScreen   — select up to 5 exercises for massed practice
  ReviewScreen         — problem → editor → test results → grade (SRS or massed)
  StatsScreen          — all exercises with stats; r=reset one, R=reset all
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from knowledge_base.code_review import db as _db_mod
from knowledge_base.code_review.cli import handle_add
from knowledge_base.code_review.db import (
    DB_PATH,
    EXERCISES_DIR,
    get_all_exercises,
    get_due_exercises,
    init_db,
    record_grade,
    reset_all_exercises,
    reset_exercise,
)
from knowledge_base.code_review.leitner import schedule as leitner_schedule
from knowledge_base.code_review.runner import compute_side_by_side_diff, run_tests


# ---------------------------------------------------------------------------
# Category and grouping helpers
# ---------------------------------------------------------------------------


def category_of(exercise: dict) -> str:
    """Return the category for an exercise — its path with the leaf slug stripped.

    Root-level exercises return "".
    """
    path = exercise.get("path") or ""
    parts = path.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def group_by_category(exercises: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group exercises by category; root category ("") first, then alphabetical.

    Within each group, exercises are sorted by slug.
    """
    by_cat: dict[str, list[dict]] = {}
    for ex in exercises:
        by_cat.setdefault(category_of(ex), []).append(ex)
    ordered = sorted(by_cat.keys(), key=lambda c: (c != "", c))
    return [(cat, sorted(by_cat[cat], key=lambda e: e["slug"])) for cat in ordered]


# ---------------------------------------------------------------------------
# SRS queue screen
# ---------------------------------------------------------------------------

class ExerciseListScreen(Screen):
    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("m", "massed_practice", "Massed"),
        Binding("s", "stats", "Stats"),
    ]

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
            lv.append(ListItem(Label("No exercises due.  m = massed practice   s = stats")))
        else:
            for ex in exercises:
                due_str = ex["due"][:10] if ex["due"] else "new"
                cat = category_of(ex)
                prefix = f"{cat} · " if cat else ""
                label = (
                    f"[{due_str}]  {prefix}{ex['slug']}  —  {ex['title']}  "
                    f"(box {ex['box']}, reps {ex['reps']})"
                )
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

    def action_massed_practice(self) -> None:
        self.app.push_screen(MassedBrowseScreen(self._conn))

    def action_stats(self) -> None:
        self.app.push_screen(StatsScreen(self._conn))


# ---------------------------------------------------------------------------
# Massed practice — exercise selection
# ---------------------------------------------------------------------------

class MassedBrowseScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    MAX_SELECT = 5

    CSS = """
    #browse-header { margin: 1 2; }
    #browse-notice { margin: 0 2 1 2; color: $warning; }
    .category-header { color: $text-muted; padding: 0 1; }
    """

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self._conn = conn
        self._exercises: list[dict] = []
        self._selected: list[dict] = []
        self._queue: deque[dict] = deque()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="browse-header")
        yield Static("", id="browse-notice")
        yield ListView(id="browse-list")
        yield Footer()

    def on_mount(self) -> None:
        self._exercises = get_all_exercises(self._conn)
        self._render_list()
        self._update_header()

    def _selected_ids(self) -> set[int]:
        return {ex["exercise_id"] for ex in self._selected}

    def _render_list(self, preserve_id: int | None = None) -> None:
        lv = self.query_one("#browse-list", ListView)
        if preserve_id is None and lv.highlighted_child is not None:
            if hasattr(lv.highlighted_child, "_exercise"):
                preserve_id = lv.highlighted_child._exercise["exercise_id"]
        lv.clear()
        ids = self._selected_ids()
        target_index: int | None = None
        flat_index = 0
        for cat, group in group_by_category(self._exercises):
            header_label = cat if cat else "(root)"
            header = ListItem(Label(f"── {header_label} ──", classes="category-header"))
            header.disabled = True
            lv.append(header)
            flat_index += 1
            for ex in group:
                marker = "[✓]" if ex["exercise_id"] in ids else "[ ]"
                due_str = ex["due"][:10] if ex["due"] else "new"
                label = (
                    f"{marker} [{due_str}]  {ex['slug']}  —  {ex['title']}  "
                    f"(box {ex['box']}, reps {ex['reps']})"
                )
                item = ListItem(Label(label))
                item._exercise = ex  # type: ignore[attr-defined]
                lv.append(item)
                if preserve_id is not None and ex["exercise_id"] == preserve_id:
                    target_index = flat_index
                flat_index += 1
        if target_index is not None:
            lv.index = target_index

    def _update_header(self) -> None:
        n = len(self._selected)
        self.query_one("#browse-header", Static).update(
            f"Massed Practice — Space to select/deselect, Enter to start   [{n}/{self.MAX_SELECT} selected]"
        )

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self.action_start_session()
        elif event.key == "space":
            event.stop()
            lv = self.query_one("#browse-list", ListView)
            item = lv.highlighted_child
            if item is None or not hasattr(item, "_exercise"):
                return
            ex = item._exercise
            ids = self._selected_ids()
            if ex["exercise_id"] in ids:
                self._selected = [e for e in self._selected if e["exercise_id"] != ex["exercise_id"]]
                self.query_one("#browse-notice", Static).update("")
            elif len(self._selected) < self.MAX_SELECT:
                self._selected.append(ex)
                self.query_one("#browse-notice", Static).update("")
            else:
                self.query_one("#browse-notice", Static).update(
                    f"Max {self.MAX_SELECT} selected. Deselect one first."
                )
            self._render_list(preserve_id=ex["exercise_id"])
            self._update_header()

    def action_start_session(self) -> None:
        if not self._selected:
            self.query_one("#browse-notice", Static).update("Select at least one exercise first.")
            return
        self._queue = deque(self._selected)
        self._do_next()

    def _do_next(self) -> None:
        if not self._queue:
            return
        self.app.push_screen(
            ReviewScreen(self._queue[0], self._conn, massed=True),
            self._on_review_done,
        )

    def _on_review_done(self, action: str | None) -> None:
        if action is None:
            return  # user escaped — end session
        if action == "again":
            self._do_next()  # redo same exercise (stays at front)
        else:
            self._queue.rotate(-1)  # move current to back, advance
            self._do_next()


# ---------------------------------------------------------------------------
# Stats + reset screen
# ---------------------------------------------------------------------------

class StatsScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "reset_one", "Reset"),
        Binding("R", "reset_all", "Reset All"),
    ]

    CSS = """
    #stats-header { margin: 1 2; }
    #confirm-bar  { margin: 0 2 1 2; color: $warning; }
    .hidden { display: none; }
    .category-header { color: $text-muted; padding: 0 1; }
    """

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self._conn = conn
        self._awaiting_confirm = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="stats-header")
        yield Static("", id="confirm-bar", classes="hidden")
        yield ListView(id="stats-list")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()

    def _reload(self) -> None:
        exercises = get_all_exercises(self._conn)
        lv = self.query_one("#stats-list", ListView)
        lv.clear()
        for cat, group in group_by_category(exercises):
            header_label = cat if cat else "(root)"
            header = ListItem(Label(f"── {header_label} ──", classes="category-header"))
            header.disabled = True
            lv.append(header)
            for ex in group:
                due  = ex["due"][:10]         if ex["due"]         else "—"
                last = ex["last_review"][:10] if ex["last_review"] else "never"
                label = (
                    f"box {ex['box']}  reps {ex['reps']:>3}  "
                    f"last {last}  next {due}    {ex['slug']}"
                )
                item = ListItem(Label(label))
                item._exercise = ex  # type: ignore[attr-defined]
                lv.append(item)
        n = len(exercises)
        self.query_one("#stats-header", Static).update(
            f"{n} exercise(s)   r = reset selected   R = reset all"
        )

    def _cancel_confirm(self) -> None:
        self._awaiting_confirm = False
        bar = self.query_one("#confirm-bar")
        bar.update("")
        bar.add_class("hidden")

    def action_reset_one(self) -> None:
        self._cancel_confirm()
        lv = self.query_one("#stats-list", ListView)
        item = lv.highlighted_child
        if item is None or not hasattr(item, "_exercise"):
            return
        ex = item._exercise
        reset_exercise(self._conn, ex["exercise_id"])
        self.notify(f"Reset: {ex['slug']}")
        self._reload()

    def action_reset_all(self) -> None:
        if not self._awaiting_confirm:
            self._awaiting_confirm = True
            bar = self.query_one("#confirm-bar")
            bar.update("Reset ALL exercises? Press R again to confirm.")
            bar.remove_class("hidden")
        else:
            self._cancel_confirm()
            reset_all_exercises(self._conn)
            self.notify("All exercises reset to new.")
            self._reload()


# ---------------------------------------------------------------------------
# Review screen — shared by SRS and massed modes
# ---------------------------------------------------------------------------

class ReviewScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    CSS = """
    #problem        { margin: 1 2; }
    #start-prompt   { margin: 0 2 1 2; color: $accent; }
    #results        { margin: 1 2; }
    #diff-row       { margin: 1 2; height: auto; }
    #diff-left-panel  { width: 1fr; padding-right: 1; border-right: tall $panel-darken-1; }
    #diff-right-panel { width: 1fr; padding-left: 1; }
    .diff-header    { color: $text-muted; margin-bottom: 1; }
    #grade-row      { height: 3; margin: 1 2; }
    #grade-row Button { margin: 0 1; }
    .hidden { display: none; }
    """

    def __init__(self, exercise: dict, conn, massed: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._exercise = exercise
        self._conn = conn
        self._massed = massed
        self._user_code = ""

    def compose(self) -> ComposeResult:
        yield Header()
        if self._massed:
            grade_row = Horizontal(
                Button("Again", id="massed-again", variant="error"),
                Button("Next",  id="massed-next",  variant="success"),
                id="grade-row",
                classes="hidden",
            )
        else:
            grade_row = Horizontal(
                Button("Again (1)", id="grade-1", variant="error"),
                Button("Hard  (2)", id="grade-2", variant="warning"),
                Button("Good  (3)", id="grade-3", variant="success"),
                Button("Easy  (4)", id="grade-4", variant="primary"),
                id="grade-row",
                classes="hidden",
            )
        yield Vertical(
            Static(id="problem"),
            Static("Press Enter to open editor.", id="start-prompt"),
            Static(id="results", classes="hidden"),
            Horizontal(
                Vertical(
                    Static("Your solution", classes="diff-header"),
                    Static(id="diff-left"),
                    id="diff-left-panel",
                ),
                Vertical(
                    Static("Reference solution", classes="diff-header"),
                    Static(id="diff-right"),
                    id="diff-right-panel",
                ),
                id="diff-row",
                classes="hidden",
            ),
            grade_row,
        )
        yield Footer()

    def on_mount(self) -> None:
        exercise_dir = EXERCISES_DIR / self._exercise["path"]
        problem_md = exercise_dir / "problem.md"
        text = (
            problem_md.read_text(encoding="utf-8")
            if problem_md.exists()
            else f"[red]Missing: {problem_md}[/red]"
        )
        self.query_one("#problem", Static).update(text)

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self.action_start_editing()

    def action_go_back(self) -> None:
        if self._massed:
            self.dismiss(None)
        else:
            self.app.pop_screen()

    def action_start_editing(self) -> None:
        self.query_one("#start-prompt").add_class("hidden")
        self.set_timer(0.05, self._open_editor)

    async def _open_editor(self) -> None:
        editor = os.environ.get("EDITOR", "vi")
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            tmpfile = Path(f.name)

        with self.app.suspend():
            subprocess.run([editor, str(tmpfile)])

        self._user_code = tmpfile.read_text()
        tmpfile.unlink(missing_ok=True)

        exercise_dir = EXERCISES_DIR / self._exercise["path"]
        passed, output = run_tests(exercise_dir, self._user_code)
        diff = compute_side_by_side_diff(self._user_code, exercise_dir / "solution.py")

        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        self.query_one("#results", Static).update(f"{status}\n\n{output}")
        self.query_one("#results").remove_class("hidden")

        if diff:
            left_text, right_text = diff
            self.query_one("#diff-left", Static).update(left_text)
            self.query_one("#diff-right", Static).update(right_text)
            self.query_one("#diff-row").remove_class("hidden")

        self.query_one("#grade-row").remove_class("hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for btn in self.query("Button"):
            btn.disabled = True

        if self._massed:
            self.dismiss("again" if event.button.id == "massed-again" else "next")
            return

        # SRS mode
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
        record_grade(
            self._conn,
            exercise_id=ex["exercise_id"],
            box=result.box,
            due=result.due,
            now=now.isoformat(),
            review={
                "exercise_id": ex["exercise_id"],
                "timestamp": now.isoformat(),
                "grade": grade,
                "prior_box": ex["box"],
                "new_box": result.box,
                "elapsed_days": elapsed_days,
            },
        )
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# App + entry point
# ---------------------------------------------------------------------------

class CodeReviewApp(App):
    def on_mount(self) -> None:
        self._conn = init_db(DB_PATH)
        if _db_mod.LAST_MIGRATION_PURGE:
            purged = ", ".join(_db_mod.LAST_MIGRATION_PURGE)
            self.notify(
                f"Migrated DB — purged pre-migration rows: {purged}",
                severity="warning",
                timeout=10,
            )
        self.push_screen(ExerciseListScreen(self._conn))

    def on_unmount(self) -> None:
        self._conn.close()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "add":
        handle_add(sys.argv[2:])
    else:
        CodeReviewApp().run()


if __name__ == "__main__":
    main()
