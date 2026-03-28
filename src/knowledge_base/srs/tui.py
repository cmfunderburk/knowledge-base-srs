"""Textual TUI for reviewing SRS cards with confidence intervals."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Static

from knowledge_base.srs.db import (
    get_due_cards,
    init_db,
    insert_review,
    update_card_scheduling,
)
from knowledge_base.srs.scheduler import (
    SUCCESS_THRESHOLD,
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
)
from knowledge_base.srs.scoring import (
    IntervalResult,
    apply_difficulty_modifier,
    score_interval,
    score_point,
)
from knowledge_base.srs.stats import brier_score, calibration_rate, point_hit_rate

# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

RANGE_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*-\s*(-?\d+\.?\d*)\s*$")
POINT_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*$")


def parse_answer(text: str) -> tuple[str, float, float | None]:
    """Parse user input into an interval or point answer.

    Returns
    -------
    tuple
        ("interval", lower, upper) or ("point", value, None).

    Raises
    ------
    ValueError
        If the input cannot be parsed or lower >= upper.
    """
    m = RANGE_RE.match(text)
    if m:
        lower, upper = float(m.group(1)), float(m.group(2))
        if lower >= upper:
            raise ValueError(f"Lower ({lower}) must be less than upper ({upper})")
        return ("interval", lower, upper)
    m = POINT_RE.match(text)
    if m:
        return ("point", float(m.group(1)), None)
    raise ValueError("Enter a range (e.g. 1000-5000) or a single number")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _format_display(value: float, prefix: str = "", decimals: int = 0) -> str:
    """Format a number with commas and an optional prefix."""
    formatted = f"{value:,.{decimals}f}"
    if prefix:
        return f"{prefix}{formatted}"
    return formatted


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
# ReviewApp
# ---------------------------------------------------------------------------


class ReviewApp(App):
    """Textual app for reviewing SRS flashcards."""

    CSS = _CSS
    TITLE = "SRS Review"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "toggle_stats", "Stats"),
    ]

    def __init__(
        self,
        db_path: str = "data/srs.db",
        deck: str | None = None,
        limit: int | None = None,
        stats_only: bool = False,
        difficulty_modifier: bool = False,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.deck_filter = deck
        self.card_limit = limit
        self.stats_only = stats_only
        self.difficulty_modifier = difficulty_modifier
        self.conn = None
        self.cards: list[dict] = []
        self.card_index: int = 0
        self.showing_answer: bool = False
        self.showing_stats: bool = False

    def _hide_input(self) -> None:
        """Hide the answer input and release focus."""
        inp = self.query_one("#answer-input", Input)
        inp.display = False
        inp.blur()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="card-header")
            yield Static("", id="question")
            yield Input(placeholder="Enter range (e.g. 1000-5000) or point estimate", id="answer-input")
            yield Static("", id="result")
            yield Static("", id="stats-display")
        yield Footer()

    def on_mount(self) -> None:
        self.conn = init_db(self.db_path)
        if self.stats_only:
            self._show_stats_screen()
            return
        now = datetime.now(timezone.utc).isoformat()
        self.cards = get_due_cards(
            self.conn, as_of=now, deck=self.deck_filter, limit=self.card_limit
        )
        if not self.cards:
            self.query_one("#card-header", Static).update("No cards due")
            self.query_one("#question", Static).update(
                "All caught up! Press q to quit."
            )
            self._hide_input()
            return
        self._show_question()

    def _show_question(self) -> None:
        """Display the current card's question."""
        card = self.cards[self.card_index]
        total = len(self.cards)
        header = f"{card['deck']} > {card['indicator_id']}  [{self.card_index + 1}/{total}]"
        self.query_one("#card-header", Static).update(header)
        self.query_one("#question", Static).update(card["question"])
        self.query_one("#result", Static).update("")
        self.query_one("#stats-display", Static).update("")
        self.showing_answer = False
        self.showing_stats = False
        inp = self.query_one("#answer-input", Input)
        inp.display = True
        inp.value = ""
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle answer submission or advance to next card."""
        if self.showing_stats:
            return

        if self.showing_answer:
            # Advance to next card
            self.card_index += 1
            if self.card_index >= len(self.cards):
                self.query_one("#card-header", Static).update("Session complete")
                self.query_one("#question", Static).update(
                    "All cards reviewed! Press q to quit or s for stats."
                )
                self._hide_input()
                self.query_one("#result", Static).update("")
                return
            self._show_question()
            return

        # Score the answer
        text = event.value.strip()
        if not text:
            return

        card = self.cards[self.card_index]
        true_answer = card["answer"]
        indicator_std = card["indicator_std"]
        indicator_mean = card["indicator_mean"]
        decimals = card.get("decimals", 0)
        prefix = card.get("unit_prefix", "")

        try:
            mode, val1, val2 = parse_answer(text)
        except ValueError as exc:
            self.query_one("#result", Static).update(f"[red]{exc}[/red]")
            return

        if indicator_std is None or indicator_std == 0:
            self.query_one("#result", Static).update(
                "[red]Card missing indicator_std; cannot score.[/red]"
            )
            return

        # --- Score ---
        if mode == "interval":
            result: IntervalResult = score_interval(val1, val2, true_answer, indicator_std)
            raw_score = result.score
            display_lines = [
                f"Answer: {_format_display(true_answer, prefix, decimals)}",
                f"Your range: {_format_display(val1, prefix, decimals)} - {_format_display(val2, prefix, decimals)}",
                f"Covered: {'Yes' if result.covered else 'No'}",
                f"Accuracy: {result.accuracy_score:.3f}  Precision: {result.precision_score:.3f}",
                f"Raw score: {raw_score:.3f}",
            ]
            review_mode = "interval"
            user_lower, user_upper, user_point_val = val1, val2, None
        else:
            raw_score = score_point(val1, true_answer, indicator_std)
            label = {1.0: "Perfect", 0.5: "Close", 0.0: "Miss"}[raw_score]
            display_lines = [
                f"Answer: {_format_display(true_answer, prefix, decimals)}",
                f"Your guess: {_format_display(val1, prefix, decimals)}",
                f"Result: {label} ({raw_score:.1f})",
            ]
            review_mode = "point"
            user_lower, user_upper, user_point_val = None, None, val1

        # Apply difficulty modifier if enabled and indicator_mean available
        score = raw_score
        if self.difficulty_modifier and indicator_mean is not None:
            score = apply_difficulty_modifier(raw_score, true_answer, indicator_mean, indicator_std)
            if score != raw_score:
                display_lines.append(f"Difficulty-adjusted score: {score:.3f}")

        # --- Schedule ---
        now_str = datetime.now(timezone.utc).isoformat()
        old_difficulty = card["difficulty"]
        old_stability = card["stability"]
        old_state = card["state"]
        consecutive = card["consecutive_successes"]

        success = score >= SUCCESS_THRESHOLD
        new_difficulty = update_difficulty(old_difficulty, score)

        # State transitions
        if old_state in ("new", "learning"):
            if success:
                consecutive += 1
            else:
                consecutive = 0

            if consecutive >= 2:
                new_state = "review"
                new_stability = 1.0
                desired_ret = compute_desired_retention(score)
                interval = compute_interval(new_stability, desired_ret)
            elif consecutive == 0:
                new_state = "learning"
                new_stability = old_stability
                interval = 0.0  # show again this session
                desired_ret = compute_desired_retention(score)
            else:
                # consecutive == 1
                new_state = "learning"
                new_stability = old_stability
                interval = 1.0  # due tomorrow
                desired_ret = compute_desired_retention(score)
        else:
            # review state
            new_stability = update_stability(old_stability, new_difficulty, score)
            desired_ret = compute_desired_retention(score)
            interval = compute_interval(new_stability, desired_ret)
            new_state = "review"
            if success:
                consecutive += 1
            else:
                consecutive = 0

        # Compute due date
        if interval == 0.0:
            due_str = now_str  # due immediately
        else:
            from datetime import timedelta

            due_dt = datetime.now(timezone.utc) + timedelta(days=interval)
            due_str = due_dt.isoformat()

        # Compute elapsed days since last review
        elapsed_days = 0.0
        if card["last_review"]:
            try:
                last_dt = datetime.fromisoformat(card["last_review"])
                elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                elapsed_days = 0.0

        # Update database
        update_card_scheduling(self.conn, card["card_id"], {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "last_review": now_str,
            "due": due_str,
            "reps": card["reps"] + 1,
            "consecutive_successes": consecutive,
            "state": new_state,
        })

        insert_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": review_mode,
            "user_lower": user_lower,
            "user_upper": user_upper,
            "user_point": user_point_val,
            "true_answer": true_answer,
            "raw_score": raw_score,
            "desired_retention": desired_ret,
            "interval_applied": interval,
            "elapsed_days": elapsed_days,
        })

        # Display scheduling info
        if interval == 0.0:
            display_lines.append("Next review: again this session")
        elif interval < 1.5:
            display_lines.append("Next review: 1 day")
        else:
            display_lines.append(f"Next review: {interval:.0f} days")

        if card.get("notes"):
            display_lines.append("")
            display_lines.append(card["notes"])

        self.query_one("#result", Static).update("\n".join(display_lines))
        self.showing_answer = True

        # Re-queue failed learning cards for intra-session repeat
        if interval == 0.0:
            refreshed = self.conn.execute(
                "SELECT * FROM cards WHERE card_id = ?", (card["card_id"],)
            ).fetchone()
            if refreshed:
                self.cards.append(dict(refreshed))

        # Hide input until next card
        self._hide_input()

    def action_toggle_stats(self) -> None:
        """Toggle the stats screen."""
        if self.showing_stats:
            # Return to current card
            if self.card_index < len(self.cards):
                self._show_question()
            else:
                self.query_one("#stats-display", Static).update("")
                self.showing_stats = False
        else:
            self._show_stats_screen()

    def _show_stats_screen(self) -> None:
        """Display aggregate statistics."""
        self.showing_stats = True
        self._hide_input()
        self.query_one("#card-header", Static).update("Statistics")
        self.query_one("#question", Static).update("")
        self.query_one("#result", Static).update("")

        # Gather reviews
        rows = self.conn.execute("SELECT * FROM review_log ORDER BY timestamp").fetchall()
        reviews = [dict(r) for r in rows]

        lines: list[str] = []

        total = len(reviews)
        lines.append(f"Total reviews: {total}")

        if total == 0:
            lines.append("No reviews recorded yet.")
            self.query_one("#stats-display", Static).update("\n".join(lines))
            return

        interval_reviews = [r for r in reviews if r["answer_mode"] == "interval"]
        point_reviews = [r for r in reviews if r["answer_mode"] == "point"]

        lines.append(f"Interval reviews: {len(interval_reviews)}")
        lines.append(f"Point reviews: {len(point_reviews)}")
        lines.append("")

        # Interval stats
        if interval_reviews:
            coverages = [
                (r["user_lower"] is not None and r["user_upper"] is not None
                 and r["user_lower"] <= r["true_answer"] <= r["user_upper"])
                for r in interval_reviews
            ]
            bs = brier_score(coverages)
            cr = calibration_rate(coverages)
            avg_score = sum(r["raw_score"] for r in interval_reviews) / len(interval_reviews)
            lines.append("--- Interval Stats ---")
            if bs is not None:
                lines.append(f"Brier score: {bs:.4f}")
            if cr is not None:
                lines.append(f"Calibration rate: {cr:.1%}")
            lines.append(f"Average score: {avg_score:.3f}")
            lines.append("")

        # Point stats
        if point_reviews:
            scores = [r["raw_score"] for r in point_reviews]
            hit_rates = point_hit_rate(scores)
            lines.append("--- Point Stats ---")
            if hit_rates is not None:
                lines.append(f"Perfect (< 5% std): {hit_rates['perfect']:.1%}")
                lines.append(f"Close (< 25% std): {hit_rates['partial']:.1%}")
                lines.append(f"Miss: {hit_rates['miss']:.1%}")
            lines.append("")

        # Card state counts
        state_rows = self.conn.execute(
            "SELECT state, COUNT(*) as cnt FROM cards GROUP BY state"
        ).fetchall()
        lines.append("--- Card States ---")
        for sr in state_rows:
            lines.append(f"  {sr['state']}: {sr['cnt']}")

        # Due today
        now = datetime.now(timezone.utc).isoformat()
        due_count = self.conn.execute(
            "SELECT COUNT(*) FROM cards WHERE (state = 'new' OR state = 'learning' OR (state = 'review' AND due <= ?))",
            (now,),
        ).fetchone()[0]
        lines.append(f"\nDue today: {due_count}")

        self.query_one("#stats-display", Static).update("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the SRS review TUI."""
    parser = argparse.ArgumentParser(description="SRS flashcard review")
    parser.add_argument("deck", nargs="?", default=None, help="Deck name to filter cards")
    parser.add_argument("--stats", action="store_true", help="Show stats screen only")
    parser.add_argument("--limit", type=int, default=None, help="Maximum cards to review")
    parser.add_argument("--db", default="data/srs.db", help="Path to SRS database (default: data/srs.db)")
    parser.add_argument("--difficulty-modifier", action="store_true", help="Enable outlier difficulty bonus")
    args = parser.parse_args()

    app = ReviewApp(
        db_path=args.db,
        deck=args.deck,
        limit=args.limit,
        stats_only=args.stats,
        difficulty_modifier=args.difficulty_modifier,
    )
    app.run()
