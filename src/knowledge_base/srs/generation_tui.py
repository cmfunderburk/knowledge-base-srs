"""Textual TUI for reviewing generation cards with masking and FSRS scheduling.

Two review modes in a single session:
1. Generation phase — masked text, binary pass/fail grading, queue-based spacing.
2. Recall phase — bare question, typed answer, 4-button FSRS grading.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Static

from knowledge_base.srs.catalog import CatalogScreen
from knowledge_base.srs.fsrs import Grade, SchedulingResult, schedule
from knowledge_base.srs.generation_db import (
    get_all_generation_cards,
    get_cards_by_ids,
    get_cards_by_readings,
    get_cards_by_source,
    get_due_generation_cards,
    get_generation_phase_cards,
    init_generation_db,
    insert_generation_review,
    update_generation_phase,
    update_generation_scheduling,
    upsert_generation_card,
)
from knowledge_base.srs.masking import mask_text
from knowledge_base.srs.text_scoring import TokenResult, compare_tokens, tokenize

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def _parse_reading_spec(spec: str) -> list[str]:
    """Parse a reading specifier like '5', '1-5', '1,3,5' into topic_id strings."""
    topic_ids: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for n in range(int(start), int(end) + 1):
                topic_ids.append(str(n))
        else:
            topic_ids.append(part)
    return topic_ids


def _section_sort_key(card: dict) -> tuple[str, int, str, int]:
    """Sort key for natural ordering across sources: (source, reading_num, suffix, card_index)."""
    section_id = card["section_id"]
    source = card.get("source", "los")
    card_index = card.get("card_index", 0)
    parts = section_id.split(".", 1)
    try:
        reading_num = int(parts[0])
    except ValueError:
        reading_num = 0
    suffix = parts[1] if len(parts) > 1 else ""
    return (source, reading_num, suffix, card_index)


def split_paste_text(text: str, split_by: str = "sentence") -> list[str]:
    """Split raw pasted text into card-sized chunks.

    Parameters
    ----------
    text:
        The raw text to split.
    split_by:
        ``"sentence"`` — split on sentence boundaries using
        ``r'(?<=[.!?])\\s+(?=[A-Z])'`` and strip each result.
        ``"line"`` — split on newlines, skipping blank lines.

    Returns
    -------
    list[str]
        Non-empty stripped strings. Empty input returns ``[]``.
    """
    if not text or not text.strip():
        return []
    if split_by == "line":
        return [line.strip() for line in text.splitlines() if line.strip()]
    # sentence splitting
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


MAX_MASKING_LEVEL = 2
PRACTICE_TYPEIN_LEVEL = 3    # virtual level for practice mode full type-in
GRADUATION_PASSES = 2       # consecutive passes at max level to graduate
GRADUATION_GAP = 5           # cards between graduation attempts
REGRESSION_INTERVAL_THRESHOLD = 1.0  # days — regress if Again interval < this


def massed_requeue_position(passed: bool, pass_count: int, queue_len: int) -> int:
    """Calculate the position to insert a card in the massed practice queue.

    Parameters
    ----------
    passed:
        Whether the card was answered correctly.
    pass_count:
        Number of qualifying passes for this card in the session.
        For masking cards, this is type-in passes only.
        For exact cards, this is total correct answers.
        A value of 0 means masking-level pass (uses 1st-pass range).
    queue_len:
        Current number of items in the queue.
    """
    if not passed:
        return 1

    if pass_count <= 1:
        low, high = 2, 4
    elif pass_count == 2:
        low, high = 4, 8
    else:
        low, high = 8, 12

    pos = random.randint(low, high)
    return min(pos, queue_len)


# ---------------------------------------------------------------------------
# Queue item
# ---------------------------------------------------------------------------


@dataclass
class QueueItem:
    """Wraps a card dict for the review queue."""

    card: dict


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _token_diff_markup(results: list[TokenResult]) -> str:
    """Build Rich markup showing a coloured word-by-word diff."""
    from rich.markup import escape

    parts: list[str] = []
    for r in results:
        if r.status == "exact":
            parts.append(f"[green]{escape(r.expected)}[/]")
        elif r.status == "close":
            parts.append(f"[yellow]{escape(r.expected)}[/]")
        elif r.status == "wrong":
            parts.append(f"[red]{escape(r.expected)}[/]")
        elif r.status == "missing":
            parts.append(f"[red]__{escape(r.expected)}__[/]")
        elif r.status == "extra":
            parts.append(f"[dim strike]{escape(r.typed)}[/]")
    return " ".join(parts)


def _interval_display(interval: float) -> str:
    """Format an interval in days to a human-readable string."""
    minutes = interval * 24 * 60
    if minutes < 60:
        return f"{minutes:.0f} min"
    if interval < 1.0:
        hours = round(interval * 24)
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if interval < 1.5:
        return "1 day"
    days = round(interval)
    return f"{days} day{'s' if days != 1 else ''}"


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
Screen {
    background: $surface;
}

#card-header {
    dock: top;
    width: 100%;
    height: auto;
    padding: 1 2;
    color: $text-muted;
}

#question {
    width: 100%;
    height: auto;
    padding: 1 2;
    text-style: bold;
}

#masked-text {
    width: 100%;
    height: auto;
    padding: 0 2 1 2;
}

#answer-input {
    width: 100%;
    margin: 1 2;
}

#result {
    width: 100%;
    height: auto;
    padding: 1 2;
}

#stats-display {
    width: 100%;
    height: auto;
    padding: 1 2;
}
"""

# ---------------------------------------------------------------------------
# GenerationReviewApp
# ---------------------------------------------------------------------------


class GenerationReviewApp(App):
    """Textual app for reviewing generation cards."""

    CSS = _CSS
    TITLE = "Generation Review"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "toggle_stats", "Stats", priority=True),
        Binding("ctrl+b", "back_to_catalog", "Catalog", priority=True),
    ]

    def __init__(
        self,
        db_path: str = "data/srs.db",
        deck: str | None = None,
        limit: int | None = None,
        stats_only: bool = False,
        practice: str | None = None,
        ordered_practice: str | None = None,
        source_filter: str | None = None,
        section_filter: str | None = None,
        topic_filter: str | None = None,
        catalog_card_ids: list[int] | None = None,
        show_catalog: bool = False,
        paste_cards: list[dict] | None = None,
        start_level: int = 0,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.deck_filter = deck
        self.card_limit = limit
        self.stats_only = stats_only
        self.practice_mode = practice is not None or ordered_practice is not None
        self.practice_spec = practice or ordered_practice  # "all", "5", "1-5", etc.
        self.ordered_practice = ordered_practice is not None
        self.source_filter = source_filter
        self.section_filter = section_filter
        self.topic_filter = topic_filter
        self.catalog_card_ids = catalog_card_ids
        self.show_catalog = show_catalog
        self.paste_cards = paste_cards
        self.start_level = min(start_level, MAX_MASKING_LEVEL)
        self._original_start_level = self.start_level
        self.conn = None
        self.queue: list[QueueItem] = []
        self.total_reviewed: int = 0
        self.total_cards: int = 0
        self._pass_counts: dict[int, int] = {}

        # State machine
        self._awaiting_gen_grade: bool = False   # waiting for pass/fail
        self._awaiting_recall_grade: bool = False  # waiting for 1/2/3/4
        self._awaiting_advance: bool = False      # waiting for space/enter to advance
        self._pending_requeue: tuple[QueueItem, int] | None = None  # (item, position)
        self._current_item: QueueItem | None = None
        self._last_diff_markup: str = ""
        self.showing_stats: bool = False

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="card-header")
            yield Static("", id="question")
            yield Static("", id="masked-text")
            yield Input(placeholder="Type the answer...", id="answer-input")
            yield Static("", id="result")
            yield Static("", id="stats-display")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.conn = init_generation_db(self.db_path)
        if self.stats_only:
            self._show_stats_screen()
            return
        if self.show_catalog:
            self.push_screen(
                CatalogScreen(self.conn, self.deck_filter),
                callback=self._on_catalog_result,
            )
            return
        if self.paste_cards is not None:
            self._build_paste_queue(self.paste_cards)
            self.total_cards = len(self.queue)
            if not self.queue:
                self._show_empty()
                return
            self._show_next()
            return
        if self.catalog_card_ids is not None:
            self._build_catalog_queue(
                self.catalog_card_ids, ordered=self.ordered_practice,
            )
            self.total_cards = len(self.queue)
            if not self.queue:
                self._show_empty()
                return
            self._show_next()
            return
        if self.source_filter is not None:
            self._build_source_filter_queue()
            self.total_cards = len(self.queue)
            if not self.queue:
                self._show_empty()
                return
            self._show_next()
            return
        if self.practice_mode:
            if self.ordered_practice:
                self._build_ordered_practice_queue()
                self.TITLE = "Ordered Practice"
            else:
                self._build_practice_queue()
                self.TITLE = "Massed Practice"
        else:
            self._build_queue()
        self.total_cards = len(self.queue)
        if not self.queue:
            self._show_empty()
            return
        self._show_next()

    def _show_empty(self) -> None:
        """Display the 'no cards' message."""
        self.query_one("#card-header", Static).update("No cards due")
        self.query_one("#question", Static).update(
            "All caught up! Press Ctrl+Q to quit."
        )
        self._hide_input()

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

    def action_back_to_catalog(self) -> None:
        """Return to the catalog screen, discarding current session."""
        if isinstance(self.screen, CatalogScreen):
            return
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

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _build_practice_queue(self) -> None:
        """Build queue for massed practice: all cards for selected readings, in-memory only."""
        if self.practice_spec == "all":
            cards = get_all_generation_cards(self.conn, deck=self.deck_filter)
        else:
            topic_ids = _parse_reading_spec(self.practice_spec)
            cards = get_cards_by_readings(
                self.conn, topic_ids=topic_ids, deck=self.deck_filter,
            )
        # In practice mode, all cards start as generation at level 0 (in-memory only)
        for c in cards:
            practice_card = dict(c)  # copy so we don't affect DB-loaded state
            practice_card["phase"] = "generation"
            practice_card["masking_level"] = self.start_level
            practice_card["consecutive_max_passes"] = 0
            self.queue.append(QueueItem(card=practice_card))

    def _build_ordered_practice_queue(self) -> None:
        """Build queue for ordered practice: cards in natural LOS order."""
        if self.practice_spec == "all":
            cards = get_all_generation_cards(self.conn, deck=self.deck_filter)
        else:
            topic_ids = _parse_reading_spec(self.practice_spec)
            cards = get_cards_by_readings(
                self.conn, topic_ids=topic_ids, deck=self.deck_filter,
            )
        cards.sort(key=_section_sort_key)
        for c in cards:
            practice_card = dict(c)
            practice_card["phase"] = "generation"
            practice_card["masking_level"] = self.start_level
            practice_card["consecutive_max_passes"] = 0
            self.queue.append(QueueItem(card=practice_card))

    def _on_catalog_result(self, result) -> None:
        """Callback from CatalogScreen dismiss — build queue from selected cards."""
        if result is None:
            self.exit()
            return
        mode, card_ids = result
        ordered = mode == "ordered"
        self.practice_mode = True
        self.ordered_practice = ordered
        self.TITLE = "Ordered Practice" if ordered else "Massed Practice"
        self._build_catalog_queue(card_ids, ordered=ordered)
        self.total_cards = len(self.queue)
        if self.queue:
            self._show_next()
        else:
            self._show_empty()

    def _build_catalog_queue(
        self, card_ids: list[int], ordered: bool = False,
    ) -> None:
        """Build a practice queue from explicit card IDs (catalog selection)."""
        cards = get_cards_by_ids(self.conn, card_ids)
        if ordered:
            cards.sort(key=_section_sort_key)
            self.TITLE = "Ordered Practice"
        else:
            random.shuffle(cards)
            self.TITLE = "Massed Practice"
        self.practice_mode = True
        self.ordered_practice = ordered
        for c in cards:
            practice_card = dict(c)
            practice_card["phase"] = "generation"
            practice_card["masking_level"] = self.start_level
            practice_card["consecutive_max_passes"] = 0
            self.queue.append(QueueItem(card=practice_card))

    def _build_paste_queue(self, cards: list[dict]) -> None:
        """Build queue from pre-built ephemeral card dicts (paste mode)."""
        self.practice_mode = True
        self.ordered_practice = False
        self.TITLE = "Paste Drill"
        for c in cards:
            self.queue.append(QueueItem(card=dict(c)))

    def _build_source_filter_queue(self) -> None:
        """Build a practice queue from --source (with optional --topic/--section)."""
        topic_ids = None
        if self.topic_filter and self.topic_filter != "all":
            topic_ids = _parse_reading_spec(self.topic_filter)

        section_ids = None
        if self.section_filter:
            section_ids = [s.strip() for s in self.section_filter.split(",")]

        cards = get_cards_by_source(
            self.conn,
            source=self.source_filter,
            topic_ids=topic_ids,
            section_ids=section_ids,
            deck=self.deck_filter,
        )
        self.practice_mode = True
        if self.ordered_practice:
            cards.sort(key=_section_sort_key)
            self.TITLE = "Ordered Practice"
        else:
            self.TITLE = "Massed Practice"
        for c in cards:
            practice_card = dict(c)
            practice_card["phase"] = "generation"
            practice_card["masking_level"] = self.start_level
            practice_card["consecutive_max_passes"] = 0
            self.queue.append(QueueItem(card=practice_card))

    def _build_queue(self) -> None:
        """Build the initial session queue from due recall + generation cards."""
        limit = self.card_limit
        now_str = datetime.now(timezone.utc).isoformat()

        # Recall-phase due cards first
        recall_cards = get_due_generation_cards(
            self.conn, as_of=now_str, deck=self.deck_filter, limit=limit,
        )
        for c in recall_cards:
            self.queue.append(QueueItem(card=c))

        remaining = None
        if limit is not None:
            remaining = max(0, limit - len(recall_cards))
            if remaining == 0:
                return

        # Generation-phase cards to fill remaining capacity
        gen_cards = get_generation_phase_cards(
            self.conn, deck=self.deck_filter, limit=remaining,
        )
        for c in gen_cards:
            self.queue.append(QueueItem(card=c))

    def _pop_next(self) -> QueueItem | None:
        """Pop the next item from the front of the queue."""
        if not self.queue:
            return None
        return self.queue.pop(0)

    def _requeue(self, item: QueueItem, position: int | None = None) -> None:
        """Re-add an item to the queue at the given position.

        For massed practice, position is calculated by massed_requeue_position.
        For ordered practice, item goes to the end (position=None).
        """
        if position is None or position >= len(self.queue):
            self.queue.append(item)
        else:
            self.queue.insert(position, item)
        self.total_cards += 1

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_next(self) -> None:
        """Advance to the next card in the queue."""
        item = self._pop_next()
        if item is None:
            self.query_one("#card-header", Static).update("Session complete")
            self.query_one("#question", Static).update(
                "All cards reviewed! Press Ctrl+Q to quit or Ctrl+S for stats."
            )
            self.query_one("#masked-text", Static).update("")
            self._hide_input()
            self.query_one("#result", Static).update("")
            self._current_item = None
            return

        self._current_item = item
        card = item.card
        phase = card["phase"]

        if phase == "generation":
            self._show_generation_card(item)
        else:
            self._show_recall_card(item)

    def _card_location(self, card: dict) -> str:
        """Build the location portion of the header from card metadata."""
        source = card.get("source", "los")
        section_id = card["section_id"]
        section_title = card.get("section_title")
        deck = card["deck"]

        if source == "los":
            return f"{deck} > {section_id}"
        elif section_title:
            return f"{deck} > {source} > {section_id}: {section_title}"
        else:
            return f"{deck} > {source} > LOS {section_id}"

    def _show_generation_card(self, item: QueueItem) -> None:
        """Display a generation-phase card with masked text."""
        card = item.card
        level = card["masking_level"]
        card_id_str = str(card["card_id"])

        progress = f"[{self.total_reviewed + 1}/{self.total_cards}]"
        location = self._card_location(card)

        # Exact-answer cards: show question, no masking, prompt for typed answer
        if card.get("card_type") == "exact":
            mode_label = "ordered" if self.ordered_practice else "practice"
            header = f"{location}  {progress}  ({mode_label} — exact)"
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            self.query_one("#masked-text", Static).update("")
            self.query_one("#result", Static).update("")
            self.query_one("#stats-display", Static).update("")
            self._awaiting_gen_grade = False
            self._awaiting_recall_grade = False
            self.showing_stats = False
            inp = self.query_one("#answer-input", Input)
            inp.display = True
            inp.value = ""
            inp.placeholder = "Type the answer..."
            inp.focus()
            return

        if self.practice_mode and level >= PRACTICE_TYPEIN_LEVEL:
            mode_label = "ordered" if self.ordered_practice else "practice"
            header = f"{location}  {progress}  ({mode_label} — type-in)"
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            self.query_one("#masked-text", Static).update("")
        elif self.practice_mode:
            mode_label = "ordered" if self.ordered_practice else "practice"
            header = (
                f"{location}  {progress}"
                f"  ({mode_label} — level {level}/{MAX_MASKING_LEVEL})"
            )
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            masked = mask_text(card["answer"], level, card_id_str)
            self.query_one("#masked-text", Static).update(masked)
        else:
            header = (
                f"{location}  {progress}"
                f"  (generation — level {level}/{MAX_MASKING_LEVEL})"
            )
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            masked = mask_text(card["answer"], level, card_id_str)
            self.query_one("#masked-text", Static).update(masked)

        self.query_one("#result", Static).update("")
        self.query_one("#stats-display", Static).update("")

        self._awaiting_gen_grade = False
        self._awaiting_recall_grade = False
        self.showing_stats = False

        inp = self.query_one("#answer-input", Input)
        inp.display = True
        inp.value = ""
        inp.placeholder = "Type the answer..."
        inp.focus()

    def _show_recall_card(self, item: QueueItem) -> None:
        """Display a recall-phase card with bare question."""
        card = item.card
        progress = f"[{self.total_reviewed + 1}/{self.total_cards}]"
        location = self._card_location(card)
        header = f"{location}  {progress}  (recall)"
        self.query_one("#card-header", Static).update(header)
        self.query_one("#question", Static).update(card["question"])
        self.query_one("#masked-text", Static).update("")

        self.query_one("#result", Static).update("")
        self.query_one("#stats-display", Static).update("")

        self._awaiting_gen_grade = False
        self._awaiting_recall_grade = False
        self.showing_stats = False

        inp = self.query_one("#answer-input", Input)
        inp.display = True
        inp.value = ""
        inp.placeholder = "Type the answer..."
        inp.focus()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _hide_input(self) -> None:
        """Hide the answer input and release focus."""
        inp = self.query_one("#answer-input", Input)
        inp.display = False
        inp.blur()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle answer submission."""
        if self.showing_stats:
            return
        if self._current_item is None:
            return
        if self._awaiting_gen_grade or self._awaiting_recall_grade or self._awaiting_advance:
            return

        text = event.value.strip()
        if not text:
            return

        card = self._current_item.card
        phase = card["phase"]

        if card.get("card_type") == "exact":
            from knowledge_base.srs.text_scoring import check_exact_answer
            correct = check_exact_answer(text, card["answer"])
            self._handle_exact_answer(correct, text)
            return

        # Tokenize and compare
        typed_tokens = tokenize(text)
        correct_tokens = tokenize(card["answer"])
        results = compare_tokens(typed_tokens, correct_tokens)
        diff_markup = _token_diff_markup(results)

        if phase == "generation":
            self._show_generation_feedback(diff_markup)
        else:
            self._show_recall_feedback(diff_markup)

    def _show_generation_feedback(self, diff_markup: str) -> None:
        """Show diff and prompt for pass/fail."""
        card = self._current_item.card
        card_id = card["card_id"]
        count = self._pass_counts.get(card_id, 0)

        lines = [
            diff_markup,
            "",
            "[dim]Correct:[/]",
            f"  {card['answer']}",
        ]

        if card["masking_level"] >= PRACTICE_TYPEIN_LEVEL and count > 0:
            if count >= 3:
                lines.append(f"  [green]Pass {count}[/]")
            else:
                lines.append(f"  Pass {count}")

        lines.append("")
        lines.append("[bold]Space/Enter[/] = Pass    [bold]f[/] = Fail")
        self.query_one("#result", Static).update("\n".join(lines))
        self._awaiting_gen_grade = True
        self._hide_input()

    def _show_recall_feedback(self, diff_markup: str) -> None:
        """Show diff and prompt for FSRS grade."""
        self._last_diff_markup = diff_markup
        lines = [
            diff_markup,
            "",
            "[dim]Correct:[/]",
            f"  {self._current_item.card['answer']}",
            "",
            "[bold]1[/]=Again  [bold]2[/]=Hard  [bold]3[/]=Good  [bold]4[/]=Easy",
        ]
        self.query_one("#result", Static).update("\n".join(lines))
        self._awaiting_recall_grade = True
        self._hide_input()

    # ------------------------------------------------------------------
    # Key handling for grading
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        """Handle grade keys after feedback is shown."""
        if self.showing_stats:
            return

        if self._awaiting_advance:
            if event.key in ("space", "enter"):
                event.prevent_default()
                self._awaiting_advance = False
                # Apply any pending re-queue
                if self._pending_requeue is not None:
                    item, position = self._pending_requeue
                    self._pending_requeue = None
                    self._requeue(item, position)
                self._advance_after_grade()
            return

        if self._awaiting_gen_grade:
            if event.key in ("space", "enter"):
                event.prevent_default()
                self._handle_generation_pass()
            elif event.key == "f":
                event.prevent_default()
                self._handle_generation_fail()
            return

        if self._awaiting_recall_grade:
            if event.key in ("1", "2", "3", "4"):
                event.prevent_default()
                grade = Grade(int(event.key))
                self._handle_recall_grade(grade)
            return

    # ------------------------------------------------------------------
    # Generation phase handlers
    # ------------------------------------------------------------------

    def _handle_generation_pass(self) -> None:
        """Handle a Pass grade for a generation-phase card."""
        item = self._current_item
        card = item.card
        level = card["masking_level"]

        if self.practice_mode:
            self._handle_practice_pass(item, card, level)
            return

        now_str = datetime.now(timezone.utc).isoformat()
        elapsed_days = self._elapsed_days(card)

        if level < MAX_MASKING_LEVEL:
            # Advance masking level, re-queue
            new_level = level + 1
            update_generation_phase(self.conn, card["card_id"], {
                "masking_level": new_level,
                "consecutive_max_passes": 0,
            })
            card["masking_level"] = new_level
            card["consecutive_max_passes"] = 0

            insert_generation_review(self.conn, {
                "card_id": card["card_id"],
                "timestamp": now_str,
                "answer_mode": "generation",
                "phase_level": level,
                "grade": None,
                "passed": 1,
                "elapsed_days": elapsed_days,
                "interval_applied": None,
            })

            self._finish_review()
            self._requeue(item, new_level + 1)
        else:
            # At max level — check for graduation
            new_passes = card["consecutive_max_passes"] + 1
            update_generation_phase(self.conn, card["card_id"], {
                "consecutive_max_passes": new_passes,
            })
            card["consecutive_max_passes"] = new_passes

            if new_passes >= GRADUATION_PASSES:
                # Graduate to recall phase
                self._graduate_card(card, now_str, elapsed_days)
                self._finish_review()
            else:
                insert_generation_review(self.conn, {
                    "card_id": card["card_id"],
                    "timestamp": now_str,
                    "answer_mode": "generation",
                    "phase_level": level,
                    "grade": None,
                    "passed": 1,
                    "elapsed_days": elapsed_days,
                    "interval_applied": None,
                })
                self._finish_review()
                self._requeue(item, GRADUATION_GAP)

    def _handle_practice_pass(
        self, item: QueueItem, card: dict, level: int
    ) -> None:
        """Handle pass in practice mode — no DB writes, no graduation."""
        card_id = card["card_id"]

        if level < MAX_MASKING_LEVEL:
            new_level = level + 1
            card["masking_level"] = new_level
            card["_practice_max_passes"] = 0
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=0, queue_len=len(self.queue),
                )
                self._requeue(item, pos)
        elif level == MAX_MASKING_LEVEL:
            # Need 2 passes at max masking before advancing to type-in
            passes = card.get("_practice_max_passes", 0) + 1
            card["_practice_max_passes"] = passes
            if passes >= 2:
                card["masking_level"] = PRACTICE_TYPEIN_LEVEL
                card["_practice_max_passes"] = 0
                self._finish_review()
                if self.ordered_practice:
                    self._requeue(item)
                else:
                    pos = massed_requeue_position(
                        passed=True, pass_count=0, queue_len=len(self.queue),
                    )
                    self._requeue(item, pos)
            else:
                self._finish_review()
                if self.ordered_practice:
                    self._requeue(item)
                else:
                    pos = massed_requeue_position(
                        passed=True, pass_count=0, queue_len=len(self.queue),
                    )
                    self._requeue(item, pos)
        else:
            # Type-in level pass — increment pass counter
            count = self._pass_counts.get(card_id, 0) + 1
            self._pass_counts[card_id] = count
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=count, queue_len=len(self.queue),
                )
                self._requeue(item, pos)

    def _handle_generation_fail(self) -> None:
        """Handle a Fail grade for a generation-phase card."""
        item = self._current_item
        card = item.card

        if self.practice_mode:
            # In-memory only: reset to level 0, re-queue soon
            card["masking_level"] = 0
            card["consecutive_max_passes"] = 0
            card["_practice_max_passes"] = 0
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                self._requeue(item, 1)
            return

        now_str = datetime.now(timezone.utc).isoformat()
        level = card["masking_level"]
        elapsed_days = self._elapsed_days(card)

        # Reset to level 0
        update_generation_phase(self.conn, card["card_id"], {
            "masking_level": 0,
            "consecutive_max_passes": 0,
        })
        card["masking_level"] = 0
        card["consecutive_max_passes"] = 0

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "generation",
            "phase_level": level,
            "grade": None,
            "passed": 0,
            "elapsed_days": elapsed_days,
            "interval_applied": None,
        })

        self._finish_review()
        self._requeue(item, 1)

    def _handle_exact_answer(self, correct: bool, typed: str) -> None:
        """Handle an exact-answer card result — auto pass/fail.

        Shows feedback and waits for Space/Enter before advancing.
        Requeue is deferred via _pending_requeue.
        """
        item = self._current_item
        card = item.card
        card_id = card["card_id"]

        if correct:
            count = self._pass_counts.get(card_id, 0) + 1
            self._pass_counts[card_id] = count

            if count >= 3:
                pass_label = f"  [green]Pass {count}[/]"
            else:
                pass_label = f"  Pass {count}"

            lines = [
                "[green]Correct![/]",
                "",
                f"[dim]Answer:[/] {card['answer']}",
                pass_label,
                "",
                "[dim]Space/Enter to continue...[/]",
            ]
            self.query_one("#result", Static).update("\n".join(lines))
            self._hide_input()
            if self.ordered_practice:
                self._pending_requeue = (item, None)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=count, queue_len=len(self.queue),
                )
                self._pending_requeue = (item, pos)
            self._awaiting_advance = True
        else:
            lines = [
                "[red]Incorrect[/]",
                "",
                f"[dim]Expected:[/] {card['answer']}",
                f"[dim]You typed:[/] {typed}",
                "",
                "[dim]Space/Enter to continue...[/]",
            ]
            self.query_one("#result", Static).update("\n".join(lines))
            self._hide_input()
            if self.ordered_practice:
                self._pending_requeue = (item, None)
            else:
                self._pending_requeue = (item, 1)
            self._awaiting_advance = True

    def _graduate_card(
        self, card: dict, now_str: str, elapsed_days: float
    ) -> None:
        """Graduate a card from generation to recall phase.

        Sets phase='recall' and performs an initial FSRS review so the card
        gets reps=1 and a due date.
        """
        now_dt = datetime.now(timezone.utc)

        # Update phase
        update_generation_phase(self.conn, card["card_id"], {
            "phase": "recall",
            "masking_level": card["masking_level"],
            "consecutive_max_passes": card["consecutive_max_passes"],
        })

        # Initial FSRS review to set reps=1 and due date
        result: SchedulingResult = schedule(
            difficulty=5.0,
            stability=0.0,
            reps=0,
            last_review=None,
            grade=Grade.GOOD,
            now=now_dt,
        )
        update_generation_scheduling(self.conn, card["card_id"], {
            "difficulty": result.difficulty,
            "stability": result.stability,
            "last_review": now_str,
            "due": result.due,
            "reps": result.reps,
        })

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "generation",
            "phase_level": card["masking_level"],
            "grade": None,
            "passed": 1,
            "elapsed_days": elapsed_days,
            "interval_applied": result.interval,
        })

    # ------------------------------------------------------------------
    # Recall phase handler
    # ------------------------------------------------------------------

    def _handle_recall_grade(self, grade: Grade) -> None:
        """Handle an FSRS grade for a recall-phase card."""
        item = self._current_item
        card = item.card
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        elapsed_days = self._elapsed_days(card)

        # Parse last_review from string to datetime
        last_review_dt = None
        if card["last_review"]:
            try:
                last_review_dt = datetime.fromisoformat(card["last_review"])
            except (ValueError, TypeError):
                last_review_dt = None

        result: SchedulingResult = schedule(
            difficulty=card["difficulty"],
            stability=card["stability"],
            reps=card["reps"],
            last_review=last_review_dt,
            grade=grade,
            now=now_dt,
        )

        update_generation_scheduling(self.conn, card["card_id"], {
            "difficulty": result.difficulty,
            "stability": result.stability,
            "last_review": now_str,
            "due": result.due,
            "reps": result.reps,
        })

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "recall",
            "phase_level": None,
            "grade": int(grade),
            "passed": None,
            "elapsed_days": elapsed_days,
            "interval_applied": result.interval,
        })

        # Show scheduling feedback replacing the grade prompt
        interval_str = _interval_display(result.interval)
        grade_name = grade.name.title()
        card = item.card
        diff_markup = self._last_diff_markup
        lines = [
            diff_markup,
            "",
            "[dim]Correct:[/]",
            f"  {card['answer']}",
            "",
            f"[bold]Grade:[/] {grade_name}    [bold]Next:[/] {interval_str}",
        ]

        # Regression rule: Again + short interval → demote to generation
        if grade == Grade.AGAIN and result.interval < REGRESSION_INTERVAL_THRESHOLD:
            update_generation_phase(self.conn, card["card_id"], {
                "phase": "generation",
                "masking_level": MAX_MASKING_LEVEL,
                "consecutive_max_passes": 0,
            })
            # Refresh card state for re-queue
            card["phase"] = "generation"
            card["masking_level"] = MAX_MASKING_LEVEL
            card["consecutive_max_passes"] = 0
            card["difficulty"] = result.difficulty
            card["stability"] = result.stability
            card["last_review"] = now_str
            card["due"] = result.due
            card["reps"] = result.reps

            lines.append("[red](regressed to generation — level 2)[/]")
            self._pending_requeue = (item, 1)

        lines.append("")
        lines.append("[dim]Space/Enter to continue...[/]")
        self.query_one("#result", Static).update("\n".join(lines))

        self._awaiting_recall_grade = False
        self._awaiting_advance = True

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _elapsed_days(self, card: dict) -> float:
        """Compute elapsed days since last review for a card."""
        if card["last_review"]:
            try:
                last_dt = datetime.fromisoformat(card["last_review"])
                return (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                pass
        return 0.0

    def _advance_after_grade(self) -> None:
        """Advance to the next card after the user has seen grade feedback."""
        self.total_reviewed += 1
        self._current_item = None
        self._show_next()

    def _finish_review(self) -> None:
        """Common cleanup after a generation review: bump counters and advance."""
        self.total_reviewed += 1
        self._awaiting_gen_grade = False
        self._awaiting_recall_grade = False
        self._current_item = None
        self._show_next()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def action_toggle_stats(self) -> None:
        """Toggle the stats screen."""
        if self.showing_stats:
            self.showing_stats = False
            if self._current_item is not None:
                card = self._current_item.card
                if card["phase"] == "generation":
                    self._show_generation_card(self._current_item)
                else:
                    self._show_recall_card(self._current_item)
            else:
                self.query_one("#stats-display", Static).update("")
                self._show_next()
        else:
            self._show_stats_screen()

    def _show_stats_screen(self) -> None:
        """Display aggregate generation card statistics."""
        self.showing_stats = True
        self._hide_input()
        self.query_one("#card-header", Static).update("Generation Stats")
        self.query_one("#question", Static).update("")
        self.query_one("#masked-text", Static).update("")
        self.query_one("#result", Static).update("")

        lines: list[str] = []

        # Card counts by phase
        total = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        gen_count = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards WHERE phase = 'generation'"
        ).fetchone()[0]
        recall_count = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards WHERE phase = 'recall'"
        ).fetchone()[0]

        lines.append(f"Total cards: {total}")
        lines.append(f"  Generation phase: {gen_count}")
        lines.append(f"  Recall phase:     {recall_count}")

        if total > 0:
            grad_rate = recall_count / total
            lines.append(f"  Graduation rate:  {grad_rate:.1%}")

        lines.append("")

        # Masking level distribution (generation cards only)
        if gen_count > 0:
            lines.append("--- Masking Level Distribution ---")
            for lvl in range(MAX_MASKING_LEVEL + 1):
                cnt = self.conn.execute(
                    "SELECT COUNT(*) FROM generation_cards "
                    "WHERE phase = 'generation' AND masking_level = ?",
                    (lvl,),
                ).fetchone()[0]
                pct = cnt / gen_count if gen_count else 0
                lines.append(f"  Level {lvl}: {cnt} ({pct:.0%})")
            lines.append("")

        # Recall grade distribution
        recall_reviews = self.conn.execute(
            "SELECT grade, COUNT(*) as cnt FROM generation_review_log "
            "WHERE answer_mode = 'recall' AND grade IS NOT NULL "
            "GROUP BY grade ORDER BY grade"
        ).fetchall()
        if recall_reviews:
            total_recall_reviews = sum(r["cnt"] for r in recall_reviews)
            lines.append("--- Recall Grade Distribution ---")
            grade_names = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
            for r in recall_reviews:
                name = grade_names.get(r["grade"], str(r["grade"]))
                pct = r["cnt"] / total_recall_reviews
                lines.append(f"  {name}: {r['cnt']} ({pct:.0%})")
            lines.append("")

        # Review log summary
        total_reviews = self.conn.execute(
            "SELECT COUNT(*) FROM generation_review_log"
        ).fetchone()[0]
        gen_reviews = self.conn.execute(
            "SELECT COUNT(*) FROM generation_review_log WHERE answer_mode = 'generation'"
        ).fetchone()[0]
        recall_review_count = self.conn.execute(
            "SELECT COUNT(*) FROM generation_review_log WHERE answer_mode = 'recall'"
        ).fetchone()[0]
        lines.append(f"Total reviews: {total_reviews}")
        lines.append(f"  Generation reviews: {gen_reviews}")
        lines.append(f"  Recall reviews:     {recall_review_count}")

        self.query_one("#stats-display", Static).update("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the generation card review TUI."""
    parser = argparse.ArgumentParser(
        description="Generation card review (CFA LOS)"
    )
    parser.add_argument("deck", nargs="?", default=None, help="Deck name to filter cards")
    parser.add_argument("--stats", action="store_true", help="Show stats screen only")
    parser.add_argument("--limit", type=int, default=None, help="Maximum cards to review")
    parser.add_argument("--db", default="data/srs.db", help="Path to SRS database")
    parser.add_argument(
        "--practice", metavar="READINGS", default=None,
        help="Massed practice mode. Specify readings: 'all', '36', '1-5', '1,3,5'. "
             "No persistent state changes — purely in-memory drill.",
    )
    parser.add_argument(
        "--ordered-practice", metavar="READINGS", default=None,
        help="Ordered practice mode. Cards cycle in fixed LOS order. "
             "Specify readings: 'all', '36', '1-5', '1,3,5'. "
             "No persistent state changes.",
    )
    parser.add_argument(
        "--source", default=None,
        help="Filter by source (e.g. 'los', 'markdown'). "
             "Launches massed practice with matching cards.",
    )
    parser.add_argument(
        "--topic", default=None, metavar="READINGS",
        help="Filter by topic (reading spec syntax: '5', '1-5', '1,3,5'). "
             "Used with --source.",
    )
    parser.add_argument(
        "--section", default=None,
        help="Filter by section ID(s), comma-separated. "
             "Used with --source.",
    )
    parser.add_argument(
        "--paste", action="store_true",
        help="Paste-and-drill mode: read text from stdin or prompt, split into cards, and drill.",
    )
    parser.add_argument(
        "--save-as", default=None,
        help="Save pasted content with this name (used with --paste).",
    )
    parser.add_argument(
        "--split-by", choices=["sentence", "line"], default="sentence",
        help="How to split pasted text into cards (default: sentence).",
    )
    parser.add_argument(
        "--start-level", type=int, default=0,
        help="Initial masking level for practice (0-2, default: 0). "
             "Use 2 to start at max masking for familiar material.",
    )
    args = parser.parse_args()

    # Determine whether to show the catalog as the entry screen.
    # Catalog is the default when no explicit mode flags are provided.
    has_explicit_mode = (
        args.practice is not None
        or args.ordered_practice is not None
        or args.paste
        or args.stats
        or args.source is not None
    )
    show_catalog = not has_explicit_mode

    # --paste: read text from stdin or prompt, split into cards, and drill
    if args.paste:
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("Paste text below (blank line to finish):")
            lines: list[str] = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line == "":
                    break
                lines.append(line)
            text = "\n".join(lines)

        card_texts = split_paste_text(text, args.split_by)
        if not card_texts:
            print("No cards generated from pasted text.")
            return

        if args.save_as is not None:
            # Persist to DB
            conn = init_generation_db(args.db)
            source = args.source or "paste"
            section_id = re.sub(r"[^a-z0-9]+", "-", args.save_as.lower()).strip("-")
            deck = args.deck or "paste"
            for i, card_text in enumerate(card_texts):
                upsert_generation_card(conn, {
                    "deck": deck,
                    "topic_id": "0",
                    "source": source,
                    "section_id": section_id,
                    "section_title": args.save_as,
                    "card_index": i,
                    "question": f"[{i + 1}/{len(card_texts)}]",
                    "answer": card_text,
                    "tags": "[]",
                })
            conn.close()
            print(f"Saved {len(card_texts)} card(s) as '{args.save_as}'.")

        # Build ephemeral card dicts (negative card_ids signal ephemeral)
        paste_card_dicts: list[dict] = []
        for i, card_text in enumerate(card_texts):
            paste_card_dicts.append({
                "card_id": -(i + 1),
                "deck": args.deck or "paste",
                "topic_id": "0",
                "source": "paste",
                "section_id": "paste",
                "section_title": None,
                "card_index": i,
                "question": f"[{i + 1}/{len(card_texts)}]",
                "answer": card_text,
                "tags": "[]",
                "masking_level": 0,
                "phase": "generation",
                "consecutive_max_passes": 0,
            })

        app = GenerationReviewApp(
            db_path=args.db,
            deck=args.deck,
            limit=args.limit,
            stats_only=False,
            catalog_card_ids=None,
            paste_cards=paste_card_dicts,
            start_level=args.start_level,
        )
        app.run()
        return

    # --source shortcut: load cards by source directly, skip catalog
    if args.source is not None:
        app = GenerationReviewApp(
            db_path=args.db,
            deck=args.deck,
            limit=args.limit,
            stats_only=False,
            ordered_practice=args.ordered_practice,
            source_filter=args.source,
            section_filter=args.section,
            topic_filter=args.topic,
            start_level=args.start_level,
        )
        app.run()
        return

    app = GenerationReviewApp(
        db_path=args.db,
        deck=args.deck,
        limit=args.limit,
        stats_only=args.stats,
        practice=args.practice,
        ordered_practice=args.ordered_practice,
        show_catalog=show_catalog,
        start_level=args.start_level,
    )
    app.run()
