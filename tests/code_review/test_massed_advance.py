"""Regression test for the massed-practice "stuck on same exercise" bug.

After the user finishes the editor and the grade row appears, focus is
typically not on any of the grade buttons (the surrounding widgets are
non-focusable Statics). If the user then presses Enter — expecting to
hit "Next" — the screen's on_key handler would re-trigger
action_start_editing and reopen the editor for the SAME exercise,
trapping the user in a loop.

The guard in ReviewScreen.on_key must skip Enter once the editor has
already returned at least once for this exercise.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App

from knowledge_base.code_review.db import add_exercise, init_db
from knowledge_base.code_review.tui import ReviewScreen


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _Harness(App):
    def __init__(self, screen):
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


@pytest.mark.anyio
async def test_enter_after_grading_does_not_reopen_editor(tmp_path, monkeypatch):
    conn = init_db(tmp_path / "t.db")
    eid = add_exercise(conn, "ex-a", "Alpha", path="ex-a")
    exercise = {"exercise_id": eid, "slug": "ex-a", "title": "Alpha", "path": "ex-a"}

    screen = ReviewScreen(exercise, conn, massed=True)
    calls: list[None] = []
    monkeypatch.setattr(screen, "action_start_editing", lambda: calls.append(None))

    app = _Harness(screen)
    async with app.run_test() as pilot:
        await pilot.pause()

        screen.on_key(SimpleNamespace(key="enter", stop=lambda: None))
        assert len(calls) == 1, "first Enter should open the editor"

        screen._editor_done = True  # simulate editor returning
        screen.on_key(SimpleNamespace(key="enter", stop=lambda: None))
        assert len(calls) == 1, (
            "Enter after editor returned must NOT reopen the editor "
            "(would trap the user when focus isn't on a grade button)"
        )
