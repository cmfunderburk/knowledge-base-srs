# Ordered Practice Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `--ordered-practice` flag to `review-gen` that presents cards in fixed LOS order (1.a, 1.b, ..., 2.a, ...) as a ring buffer — pass or fail, the card always goes to the back of the deck, preserving order across all passes.

**Architecture:** A new CLI flag `--ordered-practice` takes the same reading spec as `--practice`. Cards are loaded and sorted by natural LOS order (numeric reading, then alpha suffix). The queue uses delay=0 for all re-queues, making it a pure FIFO ring buffer. Masking progression rules (pass advances level, fail resets to 0, 2 passes at max before type-in) are unchanged — only queue position changes.

**Tech Stack:** Python 3.12+, Textual TUI, pytest

---

## File Structure

- **Modify:** `src/knowledge_base/srs/generation_tui.py` — add `_los_sort_key()`, `_build_ordered_practice_queue()`, ordered re-queue logic, CLI flag, header display
- **Create:** `tests/test_ordered_practice.py` — unit tests for sort key, queue ordering, re-queue behavior
- **Modify:** `CLAUDE.md` — add `--ordered-practice` to Quick Reference

---

### Task 1: Natural LOS sort key function

**Files:**
- Create: `tests/test_ordered_practice.py`
- Modify: `src/knowledge_base/srs/generation_tui.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ordered practice mode in generation_tui."""

from __future__ import annotations

import pytest

from knowledge_base.srs.generation_tui import _los_sort_key


class TestLosSortKey:
    def test_single_digit_reading(self):
        assert _los_sort_key({"los_id": "1.a"}) == (1, "a")

    def test_double_digit_reading(self):
        assert _los_sort_key({"los_id": "10.b"}) == (10, "b")

    def test_natural_order_across_readings(self):
        """Sorting by key puts 2.a before 10.a (not lexicographic '10' < '2')."""
        cards = [
            {"los_id": "10.a"},
            {"los_id": "2.a"},
            {"los_id": "1.c"},
            {"los_id": "1.a"},
            {"los_id": "1.b"},
        ]
        sorted_ids = [c["los_id"] for c in sorted(cards, key=_los_sort_key)]
        assert sorted_ids == ["1.a", "1.b", "1.c", "2.a", "10.a"]

    def test_within_reading_alphabetical(self):
        cards = [
            {"los_id": "5.c"},
            {"los_id": "5.a"},
            {"los_id": "5.b"},
        ]
        sorted_ids = [c["los_id"] for c in sorted(cards, key=_los_sort_key)]
        assert sorted_ids == ["5.a", "5.b", "5.c"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ordered_practice.py -v`
Expected: ImportError — `_los_sort_key` not found

- [ ] **Step 3: Implement `_los_sort_key`**

In `src/knowledge_base/srs/generation_tui.py`, add after the `_parse_reading_spec` function (around line 49):

```python
def _los_sort_key(card: dict) -> tuple[int, str]:
    """Sort key for natural LOS ordering: (reading_number, suffix)."""
    los_id = card["los_id"]
    parts = los_id.split(".", 1)
    return (int(parts[0]), parts[1] if len(parts) > 1 else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ordered_practice.py::TestLosSortKey -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_ordered_practice.py src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add _los_sort_key for natural LOS ordering"
```

---

### Task 2: Ordered practice queue building and re-queue behavior

**Files:**
- Modify: `tests/test_ordered_practice.py`
- Modify: `src/knowledge_base/srs/generation_tui.py`

This task adds the `ordered_practice` flag to `GenerationReviewApp`, builds the ordered queue, and changes re-queue to always use delay=0 in ordered mode.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ordered_practice.py`:

```python
import json
from collections import deque

from knowledge_base.srs.generation_db import init_generation_db
from knowledge_base.srs.generation_import import import_los
from knowledge_base.srs.generation_tui import (
    GenerationReviewApp,
    QueueItem,
    MAX_MASKING_LEVEL,
    PRACTICE_TYPEIN_LEVEL,
)


@pytest.fixture
def ordered_app(tmp_path):
    """Create an app in ordered practice mode with 5 cards across 2 readings."""
    data = {
        "deck": "cfa_level1",
        "readings": [
            {
                "number": 1,
                "title": "Rates and Returns",
                "book": 1,
                "los": [
                    {"id": "1.a", "text": "interpret interest rates"},
                    {"id": "1.b", "text": "explain discount rates"},
                    {"id": "1.c", "text": "calculate holding period return"},
                ],
            },
            {
                "number": 2,
                "title": "Time Value of Money",
                "book": 1,
                "los": [
                    {"id": "2.a", "text": "calculate future value"},
                    {"id": "2.b", "text": "calculate present value"},
                ],
            },
        ],
    }
    json_path = tmp_path / "los.json"
    json_path.write_text(json.dumps(data))
    db_path = tmp_path / "test.db"

    conn = init_generation_db(db_path=str(db_path))
    import_los(conn, data_path=json_path)
    conn.close()

    app = GenerationReviewApp(
        db_path=str(db_path),
        ordered_practice="1-2",
    )
    return app


class TestOrderedPracticeQueue:
    def test_queue_is_in_los_order(self, ordered_app):
        """Ordered practice queue should be sorted by natural LOS order."""
        # Manually call the queue builder (can't mount a Textual app in tests)
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        los_ids = [item.card["los_id"] for item in ordered_app.queue]
        assert los_ids == ["1.a", "1.b", "1.c", "2.a", "2.b"]

    def test_all_delays_are_zero(self, ordered_app):
        """All items in ordered queue should have delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        for item in ordered_app.queue:
            assert item.delay == 0

    def test_all_cards_start_at_level_0(self, ordered_app):
        """All cards in ordered practice start at generation level 0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        for item in ordered_app.queue:
            assert item.card["phase"] == "generation"
            assert item.card["masking_level"] == 0


class TestOrderedPracticeRequeue:
    def test_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """In ordered mode, pass should always requeue with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        # Pop the first item (1.a) and simulate a pass at level 0
        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = 0

        ordered_app._handle_practice_pass(item, card, level=0)

        # Card should be at the back of the queue
        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0
        # Should have advanced to level 1
        assert last_item.card["masking_level"] == 1

    def test_fail_requeues_at_end_with_zero_delay(self, ordered_app):
        """In ordered mode, fail should always requeue with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        # Pop the first item and simulate a fail at level 1
        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = 1

        ordered_app._handle_generation_fail()

        # Card should be at the back with delay=0
        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0
        # Should have reset to level 0
        assert last_item.card["masking_level"] == 0

    def test_order_preserved_after_multiple_reviews(self, ordered_app):
        """After popping and re-queuing several cards, order is preserved."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        original_order = [item.card["los_id"] for item in ordered_app.queue]

        # Simulate reviewing all 5 cards: pop front, push to back
        for _ in range(5):
            item = ordered_app.queue.popleft()
            ordered_app.queue.append(QueueItem(card=item.card, delay=0))

        after_cycle = [item.card["los_id"] for item in ordered_app.queue]
        assert after_cycle == original_order

    def test_typein_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """Type-in level pass in ordered mode also re-queues with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = PRACTICE_TYPEIN_LEVEL

        ordered_app._handle_practice_pass(item, card, level=PRACTICE_TYPEIN_LEVEL)

        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0

    def test_max_masking_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """Pass at max masking in ordered mode re-queues with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = MAX_MASKING_LEVEL
        card["_practice_max_passes"] = 0

        ordered_app._handle_practice_pass(item, card, level=MAX_MASKING_LEVEL)

        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ordered_practice.py::TestOrderedPracticeQueue -v`
Expected: TypeError — `__init__` doesn't accept `ordered_practice`

- [ ] **Step 3: Implement ordered practice support**

In `src/knowledge_base/srs/generation_tui.py`, make the following changes:

**3a. Add `ordered_practice` parameter to `__init__` (around line 171):**

Change the `__init__` signature and body to add the new parameter:

```python
def __init__(
    self,
    db_path: str = "data/srs.db",
    deck: str | None = None,
    limit: int | None = None,
    stats_only: bool = False,
    practice: str | None = None,
    ordered_practice: str | None = None,
) -> None:
    super().__init__()
    self.db_path = db_path
    self.deck_filter = deck
    self.card_limit = limit
    self.stats_only = stats_only
    self.practice_mode = practice is not None or ordered_practice is not None
    self.practice_spec = practice or ordered_practice
    self.ordered_practice = ordered_practice is not None
    self.conn = None
    self.queue: deque[QueueItem] = deque()
    self.total_reviewed: int = 0
    self.total_cards: int = 0

    # State machine
    self._awaiting_gen_grade: bool = False
    self._awaiting_recall_grade: bool = False
    self._awaiting_advance: bool = False
    self._pending_requeue: tuple[QueueItem, int] | None = None
    self._current_item: QueueItem | None = None
    self._last_diff_markup: str = ""
    self.showing_stats: bool = False
```

**3b. Add `_build_ordered_practice_queue` method (after `_build_practice_queue`):**

```python
def _build_ordered_practice_queue(self) -> None:
    """Build queue for ordered practice: cards in natural LOS order, all delay=0."""
    if self.practice_spec == "all":
        cards = get_all_generation_cards(self.conn, deck=self.deck_filter)
    else:
        topic_ids = _parse_reading_spec(self.practice_spec)
        cards = get_cards_by_readings(
            self.conn, topic_ids=topic_ids, deck=self.deck_filter,
        )
    cards.sort(key=_los_sort_key)
    for c in cards:
        practice_card = dict(c)
        practice_card["phase"] = "generation"
        practice_card["masking_level"] = 0
        practice_card["consecutive_max_passes"] = 0
        self.queue.append(QueueItem(card=practice_card, delay=0))
```

**3c. Update `on_mount` to use ordered queue builder (around line 224):**

Replace:

```python
if self.practice_mode:
    self._build_practice_queue()
    self.TITLE = "Massed Practice"
```

With:

```python
if self.practice_mode:
    if self.ordered_practice:
        self._build_ordered_practice_queue()
        self.TITLE = "Ordered Practice"
    else:
        self._build_practice_queue()
        self.TITLE = "Massed Practice"
```

**3d. Update `_handle_practice_pass` to use delay=0 in ordered mode:**

Replace all `self._requeue(item, ...)` calls in `_handle_practice_pass` with ordered-aware versions. Change the method to:

```python
def _handle_practice_pass(
    self, item: QueueItem, card: dict, level: int
) -> None:
    """Handle pass in practice mode — no DB writes, no graduation."""
    if level < MAX_MASKING_LEVEL:
        new_level = level + 1
        card["masking_level"] = new_level
        card["_practice_max_passes"] = 0
        self._finish_review()
        delay = 0 if self.ordered_practice else new_level + 1
        self._requeue(item, delay)
    elif level == MAX_MASKING_LEVEL:
        passes = card.get("_practice_max_passes", 0) + 1
        card["_practice_max_passes"] = passes
        if passes >= 2:
            card["masking_level"] = PRACTICE_TYPEIN_LEVEL
            card["_practice_max_passes"] = 0
            self._finish_review()
            delay = 0 if self.ordered_practice else MAX_MASKING_LEVEL + 1
            self._requeue(item, delay)
        else:
            self._finish_review()
            delay = 0 if self.ordered_practice else GRADUATION_GAP
            self._requeue(item, delay)
    else:
        # At type-in level — success, re-queue
        self._finish_review()
        delay = 0 if self.ordered_practice else len(self.queue)
        self._requeue(item, delay)
```

**3e. Update `_handle_generation_fail` practice branch to use delay=0 in ordered mode:**

Replace the practice branch (around line 615):

```python
if self.practice_mode:
    card["masking_level"] = 0
    card["consecutive_max_passes"] = 0
    card["_practice_max_passes"] = 0
    self._finish_review()
    delay = 0 if self.ordered_practice else 1
    self._requeue(item, delay)
    return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ordered_practice.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_ordered_practice.py src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add ordered practice queue with ring-buffer re-queue"
```

---

### Task 3: CLI flag, header display, and docs

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`
- Modify: `tests/test_ordered_practice.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write the failing test for header display**

Append to `tests/test_ordered_practice.py`:

```python
class TestOrderedPracticeHeader:
    def test_app_title_is_ordered_practice(self, ordered_app):
        """App title should be 'Ordered Practice' in ordered mode."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()
        # on_mount sets the title, but we can check the flag is set correctly
        assert ordered_app.ordered_practice is True
        assert ordered_app.practice_mode is True

    def test_regular_practice_flag_not_ordered(self, tmp_path):
        """Regular --practice should not set ordered_practice."""
        data = {
            "deck": "cfa_level1",
            "readings": [{
                "number": 1, "title": "Test", "book": 1,
                "los": [{"id": "1.a", "text": "test text"}],
            }],
        }
        json_path = tmp_path / "los.json"
        json_path.write_text(json.dumps(data))
        db_path = tmp_path / "test.db"
        conn = init_generation_db(db_path=str(db_path))
        import_los(conn, data_path=json_path)
        conn.close()

        app = GenerationReviewApp(
            db_path=str(db_path),
            practice="1",
        )
        assert app.practice_mode is True
        assert app.ordered_practice is False
```

- [ ] **Step 2: Run test to verify it passes** (should pass since we implemented this in Task 2)

Run: `uv run pytest tests/test_ordered_practice.py::TestOrderedPracticeHeader -v`
Expected: PASSED

- [ ] **Step 3: Add `--ordered-practice` to argparse**

In `src/knowledge_base/srs/generation_tui.py`, in the `main()` function, add after the `--practice` argument (around line 929):

```python
parser.add_argument(
    "--ordered-practice", metavar="READINGS", default=None,
    help="Ordered practice mode. Cards cycle in fixed LOS order. "
         "Specify readings: 'all', '36', '1-5', '1,3,5'. "
         "No persistent state changes.",
)
```

And update the `GenerationReviewApp` construction to pass the new arg:

```python
app = GenerationReviewApp(
    db_path=args.db,
    deck=args.deck,
    limit=args.limit,
    stats_only=args.stats,
    practice=args.practice,
    ordered_practice=args.ordered_practice,
)
```

- [ ] **Step 4: Update header text in `_show_generation_card`**

In `_show_generation_card`, the `self.practice_mode` branches (around lines 351-367) show "practice" in the header. Add an ordered-specific branch. Replace the two `if self.practice_mode` blocks with:

```python
if self.practice_mode and level >= PRACTICE_TYPEIN_LEVEL:
    mode_label = "ordered" if self.ordered_practice else "practice"
    header = (
        f"{card['deck']} > {card['los_id']}  {progress}"
        f"  ({mode_label} — type-in)"
    )
    self.query_one("#card-header", Static).update(header)
    self.query_one("#question", Static).update(card["question"])
    self.query_one("#masked-text", Static).update("")
elif self.practice_mode:
    mode_label = "ordered" if self.ordered_practice else "practice"
    header = (
        f"{card['deck']} > {card['los_id']}  {progress}"
        f"  ({mode_label} — level {level}/{MAX_MASKING_LEVEL})"
    )
    self.query_one("#card-header", Static).update(header)
    self.query_one("#question", Static).update(card["question"])
    masked = mask_text(card["answer"], level, card_id_str)
    self.query_one("#masked-text", Static).update(masked)
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/test_ordered_practice.py -v && uv run pytest --tb=short -q`
Expected: All tests pass, including existing 377+ tests

- [ ] **Step 6: Update CLAUDE.md Quick Reference**

In the "Generation cards (CFA LOS)" section of the Quick Reference, add the new flag after the existing `--practice` entries:

```markdown
uv run review-gen --ordered-practice 36   # ordered practice: single reading
uv run review-gen --ordered-practice 1-5  # ordered practice: reading range
uv run review-gen --ordered-practice 1,3,5 # ordered practice: specific readings
uv run review-gen --ordered-practice all  # ordered practice: all readings
```

In the "Generation cards (CFA LOS)" Key Constraints section, add a bullet:

```markdown
- **Ordered practice** (`--ordered-practice`): like massed practice but cards cycle in fixed LOS order (ring buffer). Pass/fail affects masking level but not queue position — card always goes to back. User drills until they quit.
```

- [ ] **Step 7: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py tests/test_ordered_practice.py CLAUDE.md
git commit -m "feat: add --ordered-practice CLI flag with docs"
```

---

### Task 4: Verify full suite and final review

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Smoke test the CLI flag parses correctly**

Run: `uv run review-gen --help`
Expected: Shows `--ordered-practice READINGS` in help output

- [ ] **Step 3: Verify no regressions in existing practice mode**

Run: `uv run pytest tests/test_generation_integration.py tests/test_generation_import.py tests/test_generation_db.py -v`
Expected: All pass
