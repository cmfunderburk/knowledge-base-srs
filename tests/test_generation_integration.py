"""Integration tests for the generation card lifecycle.

Exercises the full pipeline: import → masking progression → graduation →
FSRS scheduling → regression.  Does NOT test the TUI directly.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from knowledge_base.srs.generation_db import (
    init_generation_db,
    get_generation_card,
    update_generation_phase,
    update_generation_scheduling,
)
from knowledge_base.srs.generation_import import import_los
from knowledge_base.srs.fsrs import Grade, schedule
from knowledge_base.srs.masking import mask_text
from knowledge_base.srs.text_scoring import compare_tokens, tokenize


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def los_db(tmp_path):
    """In-memory DB with imported LOS cards (2 readings, 3 LOS)."""
    data = {
        "deck": "cfa_level1",
        "readings": [
            {
                "number": 1,
                "title": "Rates and Returns",
                "book": 1,
                "los": [
                    {
                        "id": "1.a",
                        "text": (
                            "interpret interest rates as required rates of return, "
                            "discounts, or opportunity costs"
                        ),
                    },
                    {
                        "id": "1.b",
                        "text": (
                            "explain an interest rate as the sum of a real risk-free "
                            "rate and various premiums"
                        ),
                    },
                ],
            },
            {
                "number": 2,
                "title": "Time Value of Money",
                "book": 1,
                "los": [
                    {
                        "id": "2.a",
                        "text": (
                            "calculate and interpret the future value and present "
                            "value of a single sum of money"
                        ),
                    },
                ],
            },
        ],
    }
    json_path = tmp_path / "cfa_level1_los.json"
    json_path.write_text(json.dumps(data))

    conn = init_generation_db()
    import_los(conn, data_path=json_path)
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_card_by_los(conn, los_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM generation_cards WHERE los_id = ?", (los_id,)
    ).fetchone()
    assert row is not None, f"Card not found for los_id={los_id!r}"
    return dict(row)


# ---------------------------------------------------------------------------
# TestGenerationLifecycle
# ---------------------------------------------------------------------------


class TestGenerationLifecycle:

    def test_masking_progression(self, los_db):
        """Masking gets progressively harder: level 0 < level 1 < level 2."""
        card = _get_card_by_los(los_db, "1.a")
        answer = card["answer"]
        card_id_str = str(card["card_id"])

        masked_0 = mask_text(answer, level=0, card_id=card_id_str)
        masked_1 = mask_text(answer, level=1, card_id=card_id_str)
        masked_2 = mask_text(answer, level=2, card_id=card_id_str)

        count_underscores = lambda s: s.count("_")

        u0 = count_underscores(masked_0)
        u1 = count_underscores(masked_1)
        u2 = count_underscores(masked_2)

        assert u0 < u1, f"Level 0 ({u0}) should have fewer underscores than level 1 ({u1})"
        assert u1 < u2, f"Level 1 ({u1}) should have fewer underscores than level 2 ({u2})"

    def test_graduation_flow(self, los_db):
        """Simulate progression through masking levels; card graduates to recall."""
        card = _get_card_by_los(los_db, "1.b")
        card_id = card["card_id"]

        # Initially in generation phase at level 0
        assert card["phase"] == "generation"
        assert card["masking_level"] == 0

        # Progress through masking levels
        for level in (1, 2):
            update_generation_phase(los_db, card_id, {"masking_level": level})
            row = get_generation_card(los_db, card_id)
            assert row["masking_level"] == level
            assert row["phase"] == "generation"

        # Simulate having passed level 2 twice — consecutive_max_passes reaches 2
        update_generation_phase(los_db, card_id, {"consecutive_max_passes": 2})

        # Graduation: move to recall phase
        update_generation_phase(los_db, card_id, {"phase": "recall"})

        graduated = get_generation_card(los_db, card_id)
        assert graduated["phase"] == "recall"
        assert graduated["consecutive_max_passes"] == 2

    def test_recall_scheduling(self, los_db):
        """Graduate a card; FSRS scheduling produces valid stability and intervals."""
        card = _get_card_by_los(los_db, "2.a")
        card_id = card["card_id"]

        # Graduate the card
        update_generation_phase(los_db, card_id, {"phase": "recall"})

        # --- First review (reps=0) with Grade.GOOD ---
        t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result1 = schedule(
            difficulty=card["difficulty"],
            stability=card["stability"],
            reps=0,
            last_review=None,
            grade=Grade.GOOD,
            now=t0,
        )

        assert result1.stability > 0, "Stability must be positive after first review"
        assert result1.interval > 0, "Interval must be positive after first review"
        assert result1.reps == 1

        # Persist the scheduling result
        update_generation_scheduling(los_db, card_id, {
            "difficulty": result1.difficulty,
            "stability": result1.stability,
            "reps": result1.reps,
            "last_review": t0.isoformat(),
            "due": result1.due,
        })

        # --- Second review (reps=1) with Grade.GOOD after interval days ---
        from datetime import timedelta
        t1 = t0 + timedelta(days=result1.interval)
        refreshed = get_generation_card(los_db, card_id)

        result2 = schedule(
            difficulty=refreshed["difficulty"],
            stability=refreshed["stability"],
            reps=refreshed["reps"],
            last_review=t0,
            grade=Grade.GOOD,
            now=t1,
        )

        assert result2.stability > result1.stability, (
            "Stability should increase after a second successful review "
            f"({result2.stability} > {result1.stability})"
        )
        assert result2.interval > 0
        assert result2.reps == 2

    def test_regression_on_again(self, los_db):
        """Grade.AGAIN on first recall review yields a short interval (< 1 day)."""
        card = _get_card_by_los(los_db, "1.a")
        card_id = card["card_id"]

        # Graduate the card
        update_generation_phase(los_db, card_id, {"phase": "recall"})

        t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = schedule(
            difficulty=card["difficulty"],
            stability=card["stability"],
            reps=0,
            last_review=None,
            grade=Grade.AGAIN,
            now=t0,
        )

        assert result.interval < 1.0, (
            f"Grade.AGAIN on first review should yield a short interval; got {result.interval:.4f} days"
        )

    def test_text_scoring_display(self, los_db):
        """compare_tokens produces meaningful feedback on a partial answer."""
        card = _get_card_by_los(los_db, "1.a")
        correct_answer = card["answer"]

        # Typed text: a subset of the correct answer (first five content words)
        correct_tokens = tokenize(correct_answer)
        # Use the first half of the correct tokens as the typed input
        subset_size = max(1, len(correct_tokens) // 2)
        typed_tokens = correct_tokens[:subset_size]

        results = compare_tokens(typed_tokens, correct_tokens)

        statuses = {r.status for r in results}

        # The tokens the user typed should all be exact matches
        assert "exact" in statuses, "Typed tokens should contain exact matches"

        # The remaining tokens should be missing
        assert "missing" in statuses, "Tokens beyond what was typed should be 'missing'"

        # Verify counts: first subset_size entries exact, rest missing
        exact_count = sum(1 for r in results if r.status == "exact")
        missing_count = sum(1 for r in results if r.status == "missing")

        assert exact_count == subset_size
        assert missing_count == len(correct_tokens) - subset_size
