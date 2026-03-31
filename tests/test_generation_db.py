"""Tests for srs/generation_db.py — generation cards schema and CRUD."""

import sqlite3
import pytest

from knowledge_base.srs.generation_db import (
    init_generation_db,
    insert_generation_card,
    get_generation_card,
    upsert_generation_card,
    update_generation_scheduling,
    update_generation_phase,
    get_generation_phase_cards,
    get_due_generation_cards,
    insert_generation_review,
    CURRENT_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_card(**overrides) -> dict:
    """Return a minimal valid generation card dict with sensible defaults."""
    base = {
        "deck": "cfa_level1",
        "topic_id": "1",
        "los_id": "1.a",
        "question": "What is the time value of money?",
        "answer": "Money available now is worth more than the same amount in the future.",
        "tags": "[]",
    }
    base.update(overrides)
    return base


def _minimal_review(card_id: int, **overrides) -> dict:
    """Return a minimal valid generation_review_log entry."""
    base = {
        "card_id": card_id,
        "timestamp": "2026-01-01T12:00:00",
        "answer_mode": "generation",
        "phase_level": 0,
        "grade": None,
        "passed": 1,
        "elapsed_days": 0.0,
        "interval_applied": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestSchemaInit
# ---------------------------------------------------------------------------

class TestSchemaInit:
    def test_creates_generation_cards_table(self):
        conn = init_generation_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_cards'"
        ).fetchone()
        assert result is not None

    def test_creates_generation_review_log_table(self):
        conn = init_generation_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_review_log'"
        ).fetchone()
        assert result is not None

    def test_creates_schema_version_table(self):
        conn = init_generation_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_schema_version'"
        ).fetchone()
        assert result is not None

    def test_schema_version_is_correct(self):
        conn = init_generation_db()
        row = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()
        assert row is not None
        assert row["version"] == CURRENT_SCHEMA_VERSION

    def test_current_schema_version_constant(self):
        assert CURRENT_SCHEMA_VERSION == 1

    def test_idempotent_init(self):
        """Calling init_generation_db again on same conn does not raise."""
        conn = init_generation_db()
        # Run init a second time using the same connection
        init_generation_db(conn=conn)
        row = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()
        assert row["version"] == CURRENT_SCHEMA_VERSION

    def test_indexes_exist(self):
        conn = init_generation_db()
        index_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_gen_cards_due" in index_names
        assert "idx_gen_cards_deck" in index_names
        assert "idx_gen_cards_phase" in index_names
        assert "idx_gen_review_log_card" in index_names

    def test_wal_mode_enabled(self, tmp_path):
        # WAL mode only takes effect on file-based databases; :memory: reports 'memory'
        db_file = tmp_path / "wal_test.db"
        conn = init_generation_db(db_path=str(db_file))
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_foreign_keys_enabled(self):
        conn = init_generation_db()
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_row_factory_is_sqlite_row(self):
        conn = init_generation_db()
        assert conn.row_factory == sqlite3.Row


# ---------------------------------------------------------------------------
# TestInsertAndGet
# ---------------------------------------------------------------------------

class TestInsertAndGet:
    def test_insert_and_get_round_trip(self):
        conn = init_generation_db()
        card = _minimal_card()
        card_id = insert_generation_card(conn, card)

        assert isinstance(card_id, int)
        assert card_id > 0

        retrieved = get_generation_card(conn, card_id)
        assert retrieved is not None
        assert retrieved["deck"] == "cfa_level1"
        assert retrieved["topic_id"] == "1"
        assert retrieved["los_id"] == "1.a"
        assert retrieved["question"] == "What is the time value of money?"
        assert "money" in retrieved["answer"].lower()

    def test_get_missing_card_returns_none(self):
        conn = init_generation_db()
        assert get_generation_card(conn, 9999) is None

    def test_insert_sets_defaults(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        row = get_generation_card(conn, card_id)

        assert row["masking_level"] == 0
        assert row["phase"] == "generation"
        assert row["consecutive_max_passes"] == 0
        assert row["difficulty"] == pytest.approx(5.0)
        assert row["stability"] == pytest.approx(0.0)
        assert row["reps"] == 0
        assert row["last_review"] is None
        assert row["due"] is None
        assert row["tags"] == "[]"

    def test_unique_constraint_raises(self):
        conn = init_generation_db()
        card = _minimal_card()
        insert_generation_card(conn, card)
        with pytest.raises(sqlite3.IntegrityError):
            insert_generation_card(conn, card)

    def test_upsert_inserts_new(self):
        conn = init_generation_db()
        card = _minimal_card()
        card_id = upsert_generation_card(conn, card)
        assert card_id > 0
        assert get_generation_card(conn, card_id) is not None

    def test_upsert_returns_dict_with_card_id_key(self):
        conn = init_generation_db()
        card_id = upsert_generation_card(conn, _minimal_card())
        row = get_generation_card(conn, card_id)
        assert "card_id" in row

    def test_upsert_updates_content_fields(self):
        conn = init_generation_db()
        card = _minimal_card(question="Original question?", answer="Original answer.")
        card_id = upsert_generation_card(conn, card)

        updated = _minimal_card(question="Updated question?", answer="Updated answer.")
        returned_id = upsert_generation_card(conn, updated)

        assert returned_id == card_id  # same row
        row = get_generation_card(conn, card_id)
        assert row["question"] == "Updated question?"
        assert row["answer"] == "Updated answer."

    def test_upsert_preserves_scheduling_state(self):
        """upsert_generation_card must not reset scheduling fields."""
        conn = init_generation_db()
        card = _minimal_card()
        card_id = upsert_generation_card(conn, card)

        # Simulate scheduler updating the card after a review
        update_generation_scheduling(conn, card_id, {
            "difficulty": 3.5,
            "stability": 7.5,
            "reps": 3,
            "last_review": "2026-01-01T00:00:00",
            "due": "2026-01-08T00:00:00",
        })

        # Re-import the same card (content change)
        reimported = _minimal_card(question="Revised question?")
        upsert_generation_card(conn, reimported)

        row = get_generation_card(conn, card_id)
        # Scheduling should survive
        assert row["difficulty"] == pytest.approx(3.5)
        assert row["stability"] == pytest.approx(7.5)
        assert row["reps"] == 3
        assert row["due"] == "2026-01-08T00:00:00"
        # Content should be updated
        assert row["question"] == "Revised question?"

    def test_upsert_preserves_phase_state(self):
        """upsert_generation_card must not reset phase/masking fields."""
        conn = init_generation_db()
        card_id = upsert_generation_card(conn, _minimal_card())

        update_generation_phase(conn, card_id, {
            "masking_level": 2,
            "phase": "recall",
            "consecutive_max_passes": 3,
        })

        # Re-upsert with same identity
        upsert_generation_card(conn, _minimal_card(question="New question?"))

        row = get_generation_card(conn, card_id)
        assert row["masking_level"] == 2
        assert row["phase"] == "recall"
        assert row["consecutive_max_passes"] == 3


# ---------------------------------------------------------------------------
# TestUpdatePhase
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_update_masking_level(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        update_generation_phase(conn, card_id, {"masking_level": 1})

        row = get_generation_card(conn, card_id)
        assert row["masking_level"] == 1

    def test_graduate_to_recall_phase(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        update_generation_phase(conn, card_id, {
            "masking_level": 3,
            "phase": "recall",
            "consecutive_max_passes": 5,
        })

        row = get_generation_card(conn, card_id)
        assert row["phase"] == "recall"
        assert row["masking_level"] == 3
        assert row["consecutive_max_passes"] == 5

    def test_update_phase_ignores_unknown_keys(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        # Unknown keys are silently ignored
        update_generation_phase(conn, card_id, {
            "phase": "recall",
            "nonexistent_field": "should_be_ignored",
        })

        row = get_generation_card(conn, card_id)
        assert row["phase"] == "recall"

    def test_update_phase_ignores_scheduling_keys(self):
        """Phase update must not leak into scheduling fields."""
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        # Attempt to sneak in scheduling fields — must be ignored
        update_generation_phase(conn, card_id, {
            "phase": "recall",
            "difficulty": 99.0,
        })

        row = get_generation_card(conn, card_id)
        assert row["phase"] == "recall"
        assert row["difficulty"] == pytest.approx(5.0)  # default unchanged

    def test_update_scheduling_ignores_phase_keys(self):
        """Scheduling update must not leak into phase fields."""
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        # Attempt to sneak in phase fields — must be ignored
        update_generation_scheduling(conn, card_id, {
            "reps": 5,
            "phase": "recall",
        })

        row = get_generation_card(conn, card_id)
        assert row["reps"] == 5
        assert row["phase"] == "generation"  # unchanged


# ---------------------------------------------------------------------------
# TestDueCards
# ---------------------------------------------------------------------------

class TestDueCards:
    def test_generation_phase_cards_returns_generation_phase(self):
        conn = init_generation_db()
        # Insert a generation-phase card
        gen_id = insert_generation_card(conn, _minimal_card(los_id="1.a"))
        # Insert a recall-phase card
        recall_id = insert_generation_card(conn, _minimal_card(los_id="1.b"))
        update_generation_phase(conn, recall_id, {"phase": "recall"})

        results = get_generation_phase_cards(conn)
        result_ids = [r["card_id"] for r in results]
        assert gen_id in result_ids
        assert recall_id not in result_ids

    def test_generation_phase_cards_deck_filter(self):
        conn = init_generation_db()
        id_a = insert_generation_card(conn, _minimal_card(deck="deck_a", los_id="1.a"))
        id_b = insert_generation_card(conn, _minimal_card(deck="deck_b", los_id="1.b"))

        results_a = get_generation_phase_cards(conn, deck="deck_a")
        assert len(results_a) == 1
        assert results_a[0]["card_id"] == id_a

        results_b = get_generation_phase_cards(conn, deck="deck_b")
        assert len(results_b) == 1
        assert results_b[0]["card_id"] == id_b

    def test_generation_phase_cards_limit(self):
        conn = init_generation_db()
        for i in range(5):
            insert_generation_card(conn, _minimal_card(los_id=f"1.{i}"))

        results = get_generation_phase_cards(conn, limit=3)
        assert len(results) == 3

    def test_generation_phase_cards_random_order(self):
        """Generation-phase cards should be returned in random order."""
        conn = init_generation_db()
        for i in range(20):
            insert_generation_card(conn, _minimal_card(los_id=f"los_{i}"))

        orderings = set()
        for _ in range(10):
            results = get_generation_phase_cards(conn)
            order = tuple(r["card_id"] for r in results)
            orderings.add(order)

        # With 20 cards and 10 queries, expect multiple distinct orderings
        assert len(orderings) > 1

    def test_generation_phase_cards_empty_when_all_recall(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {"phase": "recall"})

        results = get_generation_phase_cards(conn)
        assert results == []

    def test_due_generation_cards_returns_overdue_recall(self):
        conn = init_generation_db()
        # Recall-phase card overdue
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {"phase": "recall"})
        update_generation_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2026-01-01T00:00:00",
        })

        results = get_due_generation_cards(conn, as_of="2026-06-01T00:00:00")
        assert any(r["card_id"] == card_id for r in results)

    def test_due_generation_cards_excludes_future(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {"phase": "recall"})
        update_generation_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2099-01-01T00:00:00",
        })

        results = get_due_generation_cards(conn, as_of="2026-01-01T00:00:00")
        assert not any(r["card_id"] == card_id for r in results)

    def test_due_generation_cards_excludes_generation_phase(self):
        """Cards still in generation phase should not appear in due recall list."""
        conn = init_generation_db()
        # generation-phase card with a past due date set
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2026-01-01T00:00:00",
        })
        # phase is still 'generation' (default)

        results = get_due_generation_cards(conn, as_of="2026-06-01T00:00:00")
        assert not any(r["card_id"] == card_id for r in results)

    def test_due_generation_cards_ordered_by_due_asc(self):
        conn = init_generation_db()

        id_older = insert_generation_card(conn, _minimal_card(los_id="1.a"))
        update_generation_phase(conn, id_older, {"phase": "recall"})
        update_generation_scheduling(conn, id_older, {
            "reps": 1,
            "due": "2025-01-01T00:00:00",
        })

        id_newer = insert_generation_card(conn, _minimal_card(los_id="1.b"))
        update_generation_phase(conn, id_newer, {"phase": "recall"})
        update_generation_scheduling(conn, id_newer, {
            "reps": 1,
            "due": "2025-06-01T00:00:00",
        })

        results = get_due_generation_cards(conn, as_of="2026-01-01T00:00:00")
        card_ids = [r["card_id"] for r in results]
        assert card_ids.index(id_older) < card_ids.index(id_newer)

    def test_due_generation_cards_deck_filter(self):
        conn = init_generation_db()

        id_a = insert_generation_card(conn, _minimal_card(deck="deck_a", los_id="1.a"))
        update_generation_phase(conn, id_a, {"phase": "recall"})
        update_generation_scheduling(conn, id_a, {"reps": 1, "due": "2026-01-01T00:00:00"})

        id_b = insert_generation_card(conn, _minimal_card(deck="deck_b", los_id="1.b"))
        update_generation_phase(conn, id_b, {"phase": "recall"})
        update_generation_scheduling(conn, id_b, {"reps": 1, "due": "2026-01-01T00:00:00"})

        results_a = get_due_generation_cards(conn, as_of="2026-06-01T00:00:00", deck="deck_a")
        assert len(results_a) == 1
        assert results_a[0]["card_id"] == id_a

    def test_due_generation_cards_limit(self):
        conn = init_generation_db()
        for i in range(5):
            cid = insert_generation_card(conn, _minimal_card(los_id=f"los_{i}"))
            update_generation_phase(conn, cid, {"phase": "recall"})
            update_generation_scheduling(conn, cid, {"reps": 1, "due": "2026-01-01T00:00:00"})

        results = get_due_generation_cards(conn, as_of="2026-06-01T00:00:00", limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# TestReviewLog
# ---------------------------------------------------------------------------

class TestReviewLog:
    def test_insert_review_entry(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        review = _minimal_review(card_id)

        review_id = insert_generation_review(conn, review)
        assert isinstance(review_id, int)
        assert review_id > 0

    def test_insert_review_persists_fields(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        review = _minimal_review(
            card_id,
            answer_mode="generation",
            phase_level=2,
            grade=3,
            passed=1,
            elapsed_days=1.5,
            interval_applied=7.0,
        )

        review_id = insert_generation_review(conn, review)
        row = conn.execute(
            "SELECT * FROM generation_review_log WHERE review_id = ?", (review_id,)
        ).fetchone()
        row = dict(row)
        assert row["card_id"] == card_id
        assert row["answer_mode"] == "generation"
        assert row["phase_level"] == 2
        assert row["grade"] == 3
        assert row["passed"] == 1
        assert row["elapsed_days"] == pytest.approx(1.5)
        assert row["interval_applied"] == pytest.approx(7.0)

    def test_insert_review_foreign_key_enforced(self):
        """Inserting a review for a non-existent card_id must raise."""
        conn = init_generation_db()
        with pytest.raises(sqlite3.IntegrityError):
            insert_generation_review(conn, _minimal_review(card_id=9999))

    def test_insert_review_nullable_fields(self):
        """phase_level, grade, interval_applied may be NULL."""
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())
        review = _minimal_review(card_id, phase_level=None, grade=None, interval_applied=None)

        review_id = insert_generation_review(conn, review)
        row = conn.execute(
            "SELECT phase_level, grade, interval_applied FROM generation_review_log WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        assert row["phase_level"] is None
        assert row["grade"] is None
        assert row["interval_applied"] is None

    def test_insert_multiple_reviews(self):
        conn = init_generation_db()
        card_id = insert_generation_card(conn, _minimal_card())

        id1 = insert_generation_review(conn, _minimal_review(card_id, timestamp="2026-01-01T10:00:00"))
        id2 = insert_generation_review(conn, _minimal_review(card_id, timestamp="2026-02-01T10:00:00"))

        assert id1 != id2

        count = conn.execute(
            "SELECT COUNT(*) FROM generation_review_log WHERE card_id = ?", (card_id,)
        ).fetchone()[0]
        assert count == 2

    def test_file_based_db(self, tmp_path):
        """init_generation_db works with a real file path."""
        db_file = tmp_path / "gen_test.db"
        conn = init_generation_db(db_path=str(db_file))
        card_id = insert_generation_card(conn, _minimal_card())
        assert get_generation_card(conn, card_id) is not None
        conn.close()

        # Re-open and verify persistence
        conn2 = init_generation_db(db_path=str(db_file))
        row = conn2.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()
        assert row["version"] == CURRENT_SCHEMA_VERSION
        assert get_generation_card(conn2, card_id) is not None

    def test_coexists_with_srs_db_in_same_file(self, tmp_path):
        """generation tables can coexist with srs tables in the same SQLite file."""
        from knowledge_base.srs.db import init_db, insert_card, get_card

        db_file = tmp_path / "shared.db"

        # Init both schemas in the same file
        conn_srs = init_db(db_path=str(db_file))
        conn_gen = init_generation_db(db_path=str(db_file))

        # Both can write independently
        srs_card_id = insert_card(conn_srs, {
            "deck": "test_deck",
            "indicator_id": "IND001",
            "entity": "World",
            "era": "2020s",
            "question": "SRS question?",
            "answer": 42.0,
        })
        gen_card_id = insert_generation_card(conn_gen, _minimal_card())

        assert get_card(conn_srs, srs_card_id) is not None
        assert get_generation_card(conn_gen, gen_card_id) is not None
