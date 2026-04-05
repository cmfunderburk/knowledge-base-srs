# Back-to-Catalog via Ctrl+B — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to press Ctrl+B at any point during a practice session to return to a fresh catalog screen for selecting different material.

**Architecture:** Add a `_reset_session_state()` method to `GenerationReviewApp` that zeroes all session state, then `action_back_to_catalog()` calls it, clears widgets, and pushes a fresh `CatalogScreen`. Reuses the existing `_on_catalog_result` callback for the catalog→practice transition.

**Tech Stack:** Python 3.12, Textual, pytest

---

### Task 1: Add `_reset_session_state()` and `action_back_to_catalog()`

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py:241-244` (BINDINGS)
- Modify: `src/knowledge_base/srs/generation_tui.py:246-290` (__init__, store `_original_start_level`)
- Modify: `src/knowledge_base/srs/generation_tui.py` (add new methods after `_show_empty` ~line 370)
- Test: `tests/test_back_to_catalog.py`

- [ ] **Step 1: Write the failing test for `_reset_session_state`**

Create `tests/test_back_to_catalog.py`:

```python
"""Tests for back-to-catalog (Ctrl+B) feature."""

from knowledge_base.srs.generation_tui import GenerationReviewApp, QueueItem


class TestResetSessionState:
    def test_reset_clears_queue_and_counters(self):
        app = GenerationReviewApp(db_path=":memory:")
        app.queue = [QueueItem(card={"card_id": 1})]
        app.total_reviewed = 5
        app.total_cards = 10
        app._pass_counts = {1: 3, 2: 1}

        app._reset_session_state()

        assert app.queue == []
        assert app.total_reviewed == 0
        assert app.total_cards == 0
        assert app._pass_counts == {}

    def test_reset_clears_state_machine_flags(self):
        app = GenerationReviewApp(db_path=":memory:")
        app._awaiting_gen_grade = True
        app._awaiting_recall_grade = True
        app._awaiting_advance = True
        app._pending_requeue = (QueueItem(card={"card_id": 1}), 3)
        app._current_item = QueueItem(card={"card_id": 1})
        app._last_diff_markup = "some markup"
        app.showing_stats = True

        app._reset_session_state()

        assert app._awaiting_gen_grade is False
        assert app._awaiting_recall_grade is False
        assert app._awaiting_advance is False
        assert app._pending_requeue is None
        assert app._current_item is None
        assert app._last_diff_markup == ""
        assert app.showing_stats is False

    def test_reset_clears_practice_mode(self):
        app = GenerationReviewApp(db_path=":memory:")
        app.practice_mode = True
        app.ordered_practice = True

        app._reset_session_state()

        assert app.practice_mode is False
        assert app.ordered_practice is False

    def test_reset_restores_original_start_level(self):
        app = GenerationReviewApp(db_path=":memory:", start_level=2)
        app.start_level = 0  # mutated during session

        app._reset_session_state()

        assert app.start_level == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_back_to_catalog.py -v`
Expected: FAIL — `_reset_session_state` does not exist.

- [ ] **Step 3: Store `_original_start_level` in `__init__`**

In `src/knowledge_base/srs/generation_tui.py`, in `__init__`, after line 276 (`self.start_level = min(start_level, MAX_MASKING_LEVEL)`), add:

```python
        self._original_start_level = self.start_level
```

- [ ] **Step 4: Add `_reset_session_state()` method**

In `src/knowledge_base/srs/generation_tui.py`, after `_show_empty` (after line 370), add:

```python
    def _reset_session_state(self) -> None:
        """Zero out all session state for a fresh start."""
        self.queue = []
        self.total_reviewed = 0
        self.total_cards = 0
        self._pass_counts = {}
        self._awaiting_gen_grade = False
        self._awaiting_recall_grade = False
        self._awaiting_advance = False
        self._pending_requeue = None
        self._current_item = None
        self._last_diff_markup = ""
        self.showing_stats = False
        self.practice_mode = False
        self.ordered_practice = False
        self.start_level = self._original_start_level
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_back_to_catalog.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Add the binding and `action_back_to_catalog()`**

In `src/knowledge_base/srs/generation_tui.py`, update `BINDINGS` (line ~241):

```python
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "toggle_stats", "Stats", priority=True),
        Binding("ctrl+b", "back_to_catalog", "Catalog", priority=True),
    ]
```

Add the action method right after `_reset_session_state`:

```python
    def action_back_to_catalog(self) -> None:
        """Return to the catalog screen, discarding current session."""
        self._reset_session_state()
        self.query_one("#card-header", Static).update("")
        self.query_one("#question", Static).update("")
        self.query_one("#masked-text", Static).update("")
        self.query_one("#result", Static).update("")
        self.query_one("#stats-display", Static).update("")
        self._hide_input()
        self.push_screen(
            CatalogScreen(self.conn, self.deck_filter),
            callback=self._on_catalog_result,
        )
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -x -q`
Expected: All tests pass (including existing ~330 tests).

- [ ] **Step 8: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py tests/test_back_to_catalog.py
git commit -m "feat: add Ctrl+B to return to catalog from any session"
```

### Task 2: Manual smoke test

- [ ] **Step 1: Test catalog-launched session**

Run: `uv run review-gen`

1. Select some cards in the catalog, press `m` or `o` to start practice.
2. Mid-session, press `Ctrl+B`. Verify: catalog appears with fresh (no selections) state.
3. Select different material, launch practice. Verify: new session works normally.

- [ ] **Step 2: Test CLI-launched session**

Run: `uv run review-gen --practice all` (or a specific reading)

1. Mid-session, press `Ctrl+B`. Verify: catalog appears.
2. Select material and launch. Verify: works normally.

- [ ] **Step 3: Test from session-complete and empty screens**

1. In a small practice session, complete all cards until "Session complete" message.
2. Press `Ctrl+B`. Verify: catalog appears.
3. From catalog, press `q` to verify quit still works.
