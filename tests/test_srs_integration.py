"""End-to-end SRS integration tests: import -> score -> schedule -> review-log -> stats."""

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
    INITIAL_STABILITY,
)
from knowledge_base.srs.stats import brier_score, calibration_rate

FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _make_conn():
    return init_db()


def _run_import(conn):
    return import_deck(
        conn,
        deck_key="development",
        data_dir=FIXTURES,
        desc_stats_dir=FIXTURES,
        desc_stats_prefix="desc_stats_",
    )


def _find_india_card(due_cards: list[dict]) -> dict | None:
    for card in due_cards:
        if card["entity"] == "India":
            return card
    return None


# ---------------------------------------------------------------------------
# TestFullReviewCycle
# ---------------------------------------------------------------------------


class TestFullReviewCycle:
    """End-to-end: import -> score -> schedule -> review-log -> verify."""

    def test_import_review_schedule(self):
        """Import, review with good interval, verify FSRS scheduling."""
        conn = _make_conn()
        count = _run_import(conn)
        assert count == 2

        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None, "India card should be due (reps=0)"
        assert india["reps"] == 0

        card_id = india["card_id"]
        true_answer = india["answer"]  # 2389.0

        # Review with a reasonable interval
        r1 = score_interval(1000, 5000, true_answer)
        assert r1.covered is True

        # Schedule via FSRS (no state machine)
        old_difficulty = india["difficulty"]
        old_stability = india["stability"]
        assert old_stability == pytest.approx(INITIAL_STABILITY)

        new_difficulty = update_difficulty(old_difficulty, r1.score)
        new_stability = update_stability(old_stability, new_difficulty, r1.score)
        desired_ret = compute_desired_retention(r1.score)
        interval = compute_interval(new_stability, desired_ret)

        due_date = (date.today() + timedelta(days=int(interval))).isoformat()

        update_card_scheduling(conn, card_id, {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "due": due_date,
            "reps": 1,
            "last_review": TODAY,
        })

        insert_review(conn, {
            "card_id": card_id,
            "timestamp": TODAY + "T00:00:00",
            "answer_mode": "interval",
            "user_lower": 1000.0,
            "user_upper": 5000.0,
            "user_point": None,
            "true_answer": true_answer,
            "raw_score": r1.score,
            "desired_retention": desired_ret,
            "interval_applied": interval,
            "elapsed_days": 0.0,
        })

        card_after = get_card(conn, card_id)
        assert card_after is not None
        assert card_after["reps"] == 1
        assert card_after["stability"] != INITIAL_STABILITY

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 1

    def test_point_prediction_cycle(self):
        """Point prediction with exact-match answer -> score == 1.0."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        assert len(due_cards) > 0

        card = due_cards[0]
        true_answer = card["answer"]
        indicator_std = card["indicator_std"]

        score = score_point(
            user_point=true_answer,
            true_answer=true_answer,
            indicator_std=indicator_std,
        )
        assert score == pytest.approx(1.0)

    def test_stats_from_reviews(self):
        """Insert 3 reviews and verify stats functions."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        india = _find_india_card(due_cards)
        assert india is not None
        card_id = india["card_id"]
        true_answer = india["answer"]  # 2389.0

        # Review 1: (1000, 5000) — covers 2389
        r1 = score_interval(1000, 5000, true_answer)
        assert r1.covered is True

        # Review 2: (2000, 3000) — covers 2389
        r2 = score_interval(2000, 3000, true_answer)
        assert r2.covered is True

        # Review 3: (500, 600) — does NOT cover 2389
        r3 = score_interval(500, 600, true_answer)
        assert r3.covered is False

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

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 3

        coverages = [
            row["user_lower"] <= row["true_answer"] <= row["user_upper"]
            for row in reviews
        ]
        assert coverages == [True, True, False]

        bs = brier_score(coverages)
        cr = calibration_rate(coverages)

        assert bs is not None
        assert cr is not None
        assert cr == pytest.approx(2 / 3)

    def test_new_cards_start_at_initial_stability(self):
        """Imported cards should have stability = INITIAL_STABILITY."""
        conn = _make_conn()
        _run_import(conn)

        due_cards = get_due_cards(conn, as_of=TODAY)
        for card in due_cards:
            assert card["stability"] == pytest.approx(INITIAL_STABILITY)
