"""End-to-end SRS integration tests: import → score → schedule → review-log → stats."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from knowledge_base.srs.db import (
    init_db,
    get_card,
    get_due_cards,
    update_card_scheduling,
    insert_review,
    get_reviews_for_card,
)
from knowledge_base.srs.importer import import_deck
from knowledge_base.srs.scoring import score_interval, score_point
from knowledge_base.srs.scheduler import (
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
    SUCCESS_THRESHOLD,
)
from knowledge_base.srs.stats import brier_score, calibration_rate

FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _make_conn():
    """Return a fresh in-memory database."""
    return init_db()


def _run_import(conn):
    """Import the development deck from fixtures into conn."""
    return import_deck(
        conn,
        deck_key="development",
        data_dir=FIXTURES,
        desc_stats_dir=FIXTURES,
        desc_stats_prefix="desc_stats_",
    )


def _find_india_card(due_cards: list[dict]) -> dict | None:
    """Return the India card from a list of due cards, or None."""
    for card in due_cards:
        if card["entity"] == "India":
            return card
    return None


# ---------------------------------------------------------------------------
# TestFullReviewCycle
# ---------------------------------------------------------------------------


class TestFullReviewCycle:
    """End-to-end: import → score → schedule → review-log → verify state."""

    def test_import_review_schedule(self):
        """
        Two-step learning cycle: new → learning (1 success) → review (2 successes).
        """
        conn = _make_conn()

        # Step 1: import
        count = _run_import(conn)
        assert count == 2

        # Step 2: get due cards — all new cards appear
        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None, "India card should be due (state=new)"
        assert india["state"] == "new"

        card_id = india["card_id"]
        true_answer = india["answer"]          # 2389.0
        indicator_std = india["indicator_std"]  # 27142.0

        # -------------------------------------------------------
        # First review: lower=1000, upper=5000
        # Expected: new → learning, consecutive_successes=1
        # -------------------------------------------------------
        r1 = score_interval(1000, 5000, true_answer, indicator_std)
        assert r1.covered is True
        assert r1.score >= SUCCESS_THRESHOLD

        update_card_scheduling(conn, card_id, {
            "state": "learning",
            "consecutive_successes": 1,
            "due": TOMORROW,
            "reps": 1,
            "last_review": TODAY,
        })

        dr1 = compute_desired_retention(r1.score)
        interval_applied_1 = compute_interval(india["stability"], dr1)

        insert_review(conn, {
            "card_id": card_id,
            "timestamp": TODAY + "T00:00:00",
            "answer_mode": "interval",
            "user_lower": 1000.0,
            "user_upper": 5000.0,
            "user_point": None,
            "true_answer": true_answer,
            "raw_score": r1.score,
            "desired_retention": dr1,
            "interval_applied": interval_applied_1,
            "elapsed_days": 0.0,
        })

        # Verify state after first review
        card_after_1 = get_card(conn, card_id)
        assert card_after_1 is not None
        assert card_after_1["state"] == "learning"
        assert card_after_1["consecutive_successes"] == 1

        # -------------------------------------------------------
        # Second review: tighter interval 1500-3500
        # score >= 0.4 and consecutive_successes >= 1 → promote to "review"
        # -------------------------------------------------------
        r2 = score_interval(1500, 3500, true_answer, indicator_std)
        assert r2.covered is True
        assert r2.score >= SUCCESS_THRESHOLD

        assert card_after_1["consecutive_successes"] >= 1, (
            "Must have at least 1 consecutive success before promoting to review"
        )

        # Compute updated stability and new interval
        new_stability = update_stability(
            card_after_1["stability"],
            card_after_1["difficulty"],
            r2.score,
        )
        dr2 = compute_desired_retention(r2.score)
        interval_applied_2 = compute_interval(new_stability, dr2)

        update_card_scheduling(conn, card_id, {
            "state": "review",
            "stability": new_stability,
            "consecutive_successes": 2,
            "reps": 2,
            "last_review": TODAY,
            "due": (date.today() + timedelta(days=int(interval_applied_2))).isoformat(),
        })

        insert_review(conn, {
            "card_id": card_id,
            "timestamp": TODAY + "T01:00:00",
            "answer_mode": "interval",
            "user_lower": 1500.0,
            "user_upper": 3500.0,
            "user_point": None,
            "true_answer": true_answer,
            "raw_score": r2.score,
            "desired_retention": dr2,
            "interval_applied": interval_applied_2,
            "elapsed_days": 1.0,
        })

        # Verify final state
        card_after_2 = get_card(conn, card_id)
        assert card_after_2 is not None
        assert card_after_2["state"] == "review"
        assert card_after_2["reps"] == 2

        # Verify review log has two entries
        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 2

    def test_point_prediction_cycle(self):
        """
        Point prediction with exact-match answer → score == 1.0.
        """
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        assert len(due_cards) > 0, "Should have due cards after import"

        card = due_cards[0]
        true_answer = card["answer"]
        indicator_std = card["indicator_std"]

        # Score with exact match
        score = score_point(
            user_point=true_answer,
            true_answer=true_answer,
            indicator_std=indicator_std,
        )
        # error = 0 / indicator_std = 0 < 0.05 → perfect score
        assert score == pytest.approx(1.0)

    def test_stats_from_reviews(self):
        """
        Insert 3 reviews with known coverage outcomes and verify stats functions.
        """
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None
        card_id = india["card_id"]
        true_answer = india["answer"]   # 2389.0
        indicator_std = india["indicator_std"]

        # Review 1: (1000, 5000) — covers 2389
        r1 = score_interval(1000, 5000, true_answer, indicator_std)
        assert r1.covered is True

        # Review 2: (2000, 3000) — covers 2389
        r2 = score_interval(2000, 3000, true_answer, indicator_std)
        assert r2.covered is True

        # Review 3: (500, 600) — does NOT cover 2389
        r3 = score_interval(500, 600, true_answer, indicator_std)
        assert r3.covered is False

        # Insert all 3 reviews
        dr = compute_desired_retention(r1.score)
        for i, (r, lower, upper) in enumerate(
            [(r1, 1000.0, 5000.0), (r2, 2000.0, 3000.0), (r3, 500.0, 600.0)]
        ):
            insert_review(conn, {
                "card_id": card_id,
                "timestamp": f"{TODAY}T0{i}:00:00",
                "answer_mode": "interval",
                "user_lower": lower,
                "user_upper": upper,
                "user_point": None,
                "true_answer": true_answer,
                "raw_score": r.score,
                "desired_retention": compute_desired_retention(r.score),
                "interval_applied": 1.0,
                "elapsed_days": float(i),
            })

        # Retrieve review log and compute coverage list
        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 3

        coverages = [
            row["user_lower"] <= row["true_answer"] <= row["user_upper"]
            for row in reviews
        ]
        assert coverages == [True, True, False]

        # Verify stats functions return non-None values
        bs = brier_score(coverages)
        cr = calibration_rate(coverages)

        assert bs is not None
        assert cr is not None

        # 2/3 intervals covered → calibration_rate = 2/3
        assert cr == pytest.approx(2 / 3)

        # brier_score: mean of (0.95 - outcome)^2
        # outcomes: 1, 1, 0 → (0.95-1)^2, (0.95-1)^2, (0.95-0)^2
        expected_bs = ((0.95 - 1.0) ** 2 + (0.95 - 1.0) ** 2 + (0.95 - 0.0) ** 2) / 3
        assert bs == pytest.approx(expected_bs)
