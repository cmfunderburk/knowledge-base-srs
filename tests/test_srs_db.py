"""Tests for srs/db.py — SQLite schema, CRUD, and migrations."""

import sqlite3
import pytest

from knowledge_base.srs.db import (
    init_db,
    get_schema_version,
    insert_card,
    get_card,
    upsert_card,
    update_card_scheduling,
    get_due_cards,
    insert_review,
    get_reviews_for_card,
    CURRENT_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_card(**overrides) -> dict:
    """Return a minimal valid card dict with sensible defaults."""
    base = {
        "deck": "test_deck",
        "indicator_id": "IND001",
        "entity": "World",
        "era": "2020s",
        "question": "What is X?",
        "answer": 42.0,
    }
    base.update(overrides)
    return base


def _minimal_review(card_id: int, **overrides) -> dict:
    """Return a minimal valid review_log entry."""
    base = {
        "card_id": card_id,
        "timestamp": "2025-01-01T12:00:00",
        "answer_mode": "interval",
        "user_lower": 30.0,
        "user_upper": 50.0,
        "user_point": None,
        "true_answer": 42.0,
        "raw_score": 0.75,
        "desired_retention": 0.90,
        "interval_applied": 3.0,
        "elapsed_days": 0.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_version_is_one(self):
        conn = init_db()
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION

    def test_cards_table_exists(self):
        conn = init_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cards'"
        ).fetchone()
        assert result is not None

    def test_review_log_table_exists(self):
        conn = init_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='review_log'"
        ).fetchone()
        assert result is not None

    def test_schema_version_table_exists(self):
        conn = init_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        assert result is not None

    def test_init_is_idempotent(self):
        """Calling init_db twice on same in-memory DB does not raise."""
        conn = init_db()
        # Simulate re-running migration by calling _migrate again
        from knowledge_base.srs.db import _migrate
        _migrate(conn)
        assert get_schema_version(conn) == 1

    def test_indexes_exist(self):
        conn = init_db()
        index_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_cards_due" in index_names
        assert "idx_cards_deck" in index_names
        assert "idx_review_log_card" in index_names
        assert "idx_review_log_timestamp" in index_names


# ---------------------------------------------------------------------------
# TestCardCRUD
# ---------------------------------------------------------------------------

class TestCardCRUD:
    def test_insert_and_get(self):
        conn = init_db()
        card = _minimal_card()
        card_id = insert_card(conn, card)
        assert isinstance(card_id, int)
        assert card_id > 0

        retrieved = get_card(conn, card_id)
        assert retrieved is not None
        assert retrieved["indicator_id"] == "IND001"
        assert retrieved["entity"] == "World"
        assert retrieved["answer"] == pytest.approx(42.0)

    def test_get_missing_card_returns_none(self):
        conn = init_db()
        assert get_card(conn, 9999) is None

    def test_insert_sets_defaults(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        row = get_card(conn, card_id)
        assert row["state"] == "new"
        assert row["reps"] == 0
        assert row["difficulty"] == pytest.approx(0.3)
        assert row["stability"] == pytest.approx(1.0)
        assert row["consecutive_successes"] == 0
        assert row["unit_prefix"] == ""
        assert row["unit_label"] == ""

    def test_unique_constraint_raises(self):
        conn = init_db()
        card = _minimal_card()
        insert_card(conn, card)
        with pytest.raises(sqlite3.IntegrityError):
            insert_card(conn, card)

    def test_upsert_inserts_new(self):
        conn = init_db()
        card = _minimal_card()
        card_id = upsert_card(conn, card)
        assert card_id > 0
        assert get_card(conn, card_id) is not None

    def test_upsert_updates_content_fields(self):
        conn = init_db()
        card = _minimal_card(question="Original question?", answer=10.0)
        card_id = upsert_card(conn, card)

        updated = _minimal_card(question="Updated question?", answer=20.0)
        returned_id = upsert_card(conn, updated)

        assert returned_id == card_id  # same row
        row = get_card(conn, card_id)
        assert row["question"] == "Updated question?"
        assert row["answer"] == pytest.approx(20.0)

    def test_upsert_preserves_scheduling_state(self):
        """upsert_card must not reset scheduling fields set by the scheduler."""
        conn = init_db()
        card = _minimal_card()
        card_id = upsert_card(conn, card)

        # Simulate scheduler updating the card after a review
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "difficulty": 0.55,
            "stability": 7.5,
            "reps": 3,
            "consecutive_successes": 2,
            "last_review": "2025-01-01T00:00:00",
            "due": "2025-01-08T00:00:00",
        })

        # Re-import the same card (content change)
        reimported = _minimal_card(question="Revised question?")
        upsert_card(conn, reimported)

        row = get_card(conn, card_id)
        # Scheduling should survive
        assert row["state"] == "review"
        assert row["difficulty"] == pytest.approx(0.55)
        assert row["stability"] == pytest.approx(7.5)
        assert row["reps"] == 3
        assert row["consecutive_successes"] == 2
        # Content should be updated
        assert row["question"] == "Revised question?"


# ---------------------------------------------------------------------------
# TestScheduling
# ---------------------------------------------------------------------------

class TestScheduling:
    def test_update_scheduling_fields(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        update_card_scheduling(conn, card_id, {
            "state": "learning",
            "difficulty": 0.4,
            "stability": 2.5,
            "reps": 1,
            "consecutive_successes": 1,
            "due": "2025-06-01T00:00:00",
        })

        row = get_card(conn, card_id)
        assert row["state"] == "learning"
        assert row["difficulty"] == pytest.approx(0.4)
        assert row["stability"] == pytest.approx(2.5)
        assert row["reps"] == 1
        assert row["due"] == "2025-06-01T00:00:00"

    def test_update_scheduling_ignores_unknown_keys(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        # Should not raise even with unknown/non-scheduling keys
        update_card_scheduling(conn, card_id, {"question": "hacked?", "reps": 5})
        row = get_card(conn, card_id)
        # 'question' is not a scheduling field — must be unchanged
        assert row["question"] == "What is X?"
        assert row["reps"] == 5

    def test_get_due_cards_returns_new_cards(self):
        """New cards always appear in the due list."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        assert len(due) == 1
        assert due[0]["card_id"] == card_id

    def test_get_due_cards_returns_overdue_review(self):
        """A review card whose due date is in the past should appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "due": "2025-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-06-01T00:00:00")
        assert any(c["card_id"] == card_id for c in due)

    def test_get_due_cards_excludes_future_review(self):
        """A review card due in the future must not appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "due": "2099-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        assert not any(c["card_id"] == card_id for c in due)

    def test_get_due_cards_filters_by_deck(self):
        conn = init_db()
        id_a = insert_card(conn, _minimal_card(deck="deck_a"))
        id_b = insert_card(conn, _minimal_card(
            deck="deck_b", indicator_id="IND002"
        ))

        due_a = get_due_cards(conn, as_of="2025-01-01T00:00:00", deck="deck_a")
        assert len(due_a) == 1
        assert due_a[0]["card_id"] == id_a

        due_b = get_due_cards(conn, as_of="2025-01-01T00:00:00", deck="deck_b")
        assert len(due_b) == 1
        assert due_b[0]["card_id"] == id_b

    def test_get_due_cards_limit(self):
        conn = init_db()
        for i in range(5):
            insert_card(conn, _minimal_card(
                indicator_id=f"IND{i:03d}",
                entity=f"Entity{i}",
            ))

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00", limit=3)
        assert len(due) == 3

    def test_get_due_cards_priority_ordering(self):
        """learning(cs=0) < overdue review < learning(cs>=1) < new."""
        conn = init_db()

        new_id = insert_card(conn, _minimal_card(indicator_id="NEW001"))

        learning_step1_id = insert_card(conn, _minimal_card(
            indicator_id="LRN001", entity="E1"
        ))
        update_card_scheduling(conn, learning_step1_id, {
            "state": "learning",
            "consecutive_successes": 0,
        })

        review_id = insert_card(conn, _minimal_card(
            indicator_id="REV001", entity="E2"
        ))
        update_card_scheduling(conn, review_id, {
            "state": "review",
            "due": "2020-01-01T00:00:00",
        })

        learning_step2_id = insert_card(conn, _minimal_card(
            indicator_id="LRN002", entity="E3"
        ))
        update_card_scheduling(conn, learning_step2_id, {
            "state": "learning",
            "consecutive_successes": 1,
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        card_ids = [c["card_id"] for c in due]

        # learning step-1 first
        assert card_ids.index(learning_step1_id) < card_ids.index(review_id)
        # overdue review before learning step-2
        assert card_ids.index(review_id) < card_ids.index(learning_step2_id)
        # learning step-2 before new
        assert card_ids.index(learning_step2_id) < card_ids.index(new_id)


# ---------------------------------------------------------------------------
# TestReviewLog
# ---------------------------------------------------------------------------

class TestReviewLog:
    def test_insert_and_retrieve(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        review = _minimal_review(card_id)

        review_id = insert_review(conn, review)
        assert isinstance(review_id, int)
        assert review_id > 0

        reviews = get_reviews_for_card(conn, card_id)
        assert len(reviews) == 1
        assert reviews[0]["review_id"] == review_id
        assert reviews[0]["card_id"] == card_id
        assert reviews[0]["raw_score"] == pytest.approx(0.75)

    def test_multiple_reviews_ordered_by_timestamp(self):
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        insert_review(conn, _minimal_review(card_id, timestamp="2025-03-01T10:00:00"))
        insert_review(conn, _minimal_review(card_id, timestamp="2025-01-01T10:00:00"))
        insert_review(conn, _minimal_review(card_id, timestamp="2025-06-01T10:00:00"))

        reviews = get_reviews_for_card(conn, card_id)
        timestamps = [r["timestamp"] for r in reviews]
        assert timestamps == sorted(timestamps)

    def test_get_reviews_empty_for_unknown_card(self):
        conn = init_db()
        assert get_reviews_for_card(conn, 9999) == []

    def test_foreign_key_enforced(self):
        """Inserting a review for a non-existent card_id must raise."""
        conn = init_db()
        with pytest.raises(sqlite3.IntegrityError):
            insert_review(conn, _minimal_review(card_id=9999))

    def test_file_based_db(self, tmp_path):
        """init_db works with a real file path."""
        db_file = tmp_path / "test.db"
        conn = init_db(db_file)
        assert get_schema_version(conn) == 1
        card_id = insert_card(conn, _minimal_card())
        assert get_card(conn, card_id) is not None
        conn.close()

        # Re-open and verify persistence
        conn2 = init_db(db_file)
        assert get_schema_version(conn2) == 1
        assert get_card(conn2, card_id) is not None
