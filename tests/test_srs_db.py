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
    _migrate,
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


def _create_v1_db(db_path=":memory:") -> sqlite3.Connection:
    """Manually create a v1 database for migration testing."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")

    with conn:
        conn.execute("""
            CREATE TABLE schema_version (version INTEGER NOT NULL)
        """)
        conn.execute("""
            CREATE TABLE cards (
                card_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                deck                    TEXT    NOT NULL,
                indicator_id            TEXT    NOT NULL,
                entity                  TEXT    NOT NULL,
                era                     TEXT    NOT NULL,
                question                TEXT    NOT NULL,
                answer                  REAL    NOT NULL,
                unit_prefix             TEXT    NOT NULL DEFAULT '',
                unit_label              TEXT    NOT NULL DEFAULT '',
                notes                   TEXT    NOT NULL DEFAULT '',
                tags                    TEXT    NOT NULL DEFAULT '[]',
                indicator_mean          REAL,
                indicator_std           REAL,
                scale_factor            INTEGER NOT NULL DEFAULT 1,
                decimals                INTEGER NOT NULL DEFAULT 0,
                difficulty              REAL    NOT NULL DEFAULT 0.3,
                stability               REAL    NOT NULL DEFAULT 1.0,
                last_review             TEXT,
                due                     TEXT,
                reps                    INTEGER NOT NULL DEFAULT 0,
                consecutive_successes   INTEGER NOT NULL DEFAULT 0,
                state                   TEXT    NOT NULL DEFAULT 'new',
                UNIQUE (indicator_id, entity, era)
            )
        """)
        conn.execute("""
            CREATE TABLE review_log (
                review_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id             INTEGER NOT NULL REFERENCES cards(card_id),
                timestamp           TEXT    NOT NULL,
                answer_mode         TEXT    NOT NULL,
                user_lower          REAL,
                user_upper          REAL,
                user_point          REAL,
                true_answer         REAL    NOT NULL,
                raw_score           REAL    NOT NULL,
                desired_retention   REAL    NOT NULL,
                interval_applied    REAL    NOT NULL,
                elapsed_days        REAL    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_due  ON cards (due, state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards (deck)")
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")

    return conn


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_version_is_two(self):
        conn = init_db()
        assert get_schema_version(conn) == 2

    def test_current_schema_version_constant(self):
        assert CURRENT_SCHEMA_VERSION == 2

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

    def test_no_state_column(self):
        conn = init_db()
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "state" not in cols

    def test_no_consecutive_successes_column(self):
        conn = init_db()
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "consecutive_successes" not in cols

    def test_init_is_idempotent(self):
        """Calling _migrate again on a v2 DB does not raise or change version."""
        conn = init_db()
        _migrate(conn)
        assert get_schema_version(conn) == 2

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
        assert row["reps"] == 0
        assert row["difficulty"] == pytest.approx(0.3)
        assert row["stability"] == pytest.approx(0.5)
        assert "state" not in row
        assert "consecutive_successes" not in row
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
            "difficulty": 0.55,
            "stability": 7.5,
            "reps": 3,
            "last_review": "2025-01-01T00:00:00",
            "due": "2025-01-08T00:00:00",
        })

        # Re-import the same card (content change)
        reimported = _minimal_card(question="Revised question?")
        upsert_card(conn, reimported)

        row = get_card(conn, card_id)
        # Scheduling should survive
        assert row["difficulty"] == pytest.approx(0.55)
        assert row["stability"] == pytest.approx(7.5)
        assert row["reps"] == 3
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
            "difficulty": 0.4,
            "stability": 2.5,
            "reps": 1,
            "due": "2025-06-01T00:00:00",
        })

        row = get_card(conn, card_id)
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

    def test_update_scheduling_ignores_removed_fields(self):
        """state and consecutive_successes are silently ignored."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        # Must not raise even though these columns no longer exist
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "consecutive_successes": 2,
            "reps": 4,
        })
        row = get_card(conn, card_id)
        assert row["reps"] == 4
        assert "state" not in row
        assert "consecutive_successes" not in row

    def test_get_due_cards_returns_new_cards(self):
        """New cards (reps=0) always appear in the due list."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        assert len(due) == 1
        assert due[0]["card_id"] == card_id

    def test_get_due_cards_returns_overdue(self):
        """A card with reps>0 whose due date is in the past should appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "reps": 1,
            "due": "2025-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-06-01T00:00:00")
        assert any(c["card_id"] == card_id for c in due)

    def test_get_due_cards_excludes_future(self):
        """A card with reps>0 due in the future must not appear."""
        conn = init_db()
        card_id = insert_card(conn, _minimal_card())
        update_card_scheduling(conn, card_id, {
            "reps": 1,
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

    def test_get_due_cards_overdue_before_new(self):
        """Overdue cards (reps>0, due<=now) must come before new cards (reps=0)."""
        conn = init_db()

        new_id = insert_card(conn, _minimal_card(indicator_id="NEW001"))

        overdue_id = insert_card(conn, _minimal_card(
            indicator_id="OVR001", entity="E1"
        ))
        update_card_scheduling(conn, overdue_id, {
            "reps": 2,
            "due": "2020-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        card_ids = [c["card_id"] for c in due]

        assert card_ids.index(overdue_id) < card_ids.index(new_id)

    def test_get_due_cards_overdue_ordered_by_due_asc(self):
        """Among overdue cards, oldest due date comes first."""
        conn = init_db()

        id_older = insert_card(conn, _minimal_card(indicator_id="OVR001"))
        update_card_scheduling(conn, id_older, {
            "reps": 1,
            "due": "2010-01-01T00:00:00",
        })

        id_newer = insert_card(conn, _minimal_card(
            indicator_id="OVR002", entity="E2"
        ))
        update_card_scheduling(conn, id_newer, {
            "reps": 1,
            "due": "2024-01-01T00:00:00",
        })

        due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
        card_ids = [c["card_id"] for c in due]
        assert card_ids.index(id_older) < card_ids.index(id_newer)

    def test_new_cards_randomized(self):
        """New cards should be returned in random order across repeated queries."""
        conn = init_db()
        for i in range(20):
            insert_card(conn, _minimal_card(
                indicator_id=f"IND{i:03d}",
                entity=f"Entity{i}",
            ))

        orderings = set()
        for _ in range(10):
            due = get_due_cards(conn, as_of="2025-01-01T00:00:00")
            order = tuple(c["card_id"] for c in due)
            orderings.add(order)

        # With 20 cards and 10 queries, we expect multiple distinct orderings
        assert len(orderings) > 1


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
        """init_db works with a real file path and version is 2."""
        db_file = tmp_path / "test.db"
        conn = init_db(db_file)
        assert get_schema_version(conn) == 2
        card_id = insert_card(conn, _minimal_card())
        assert get_card(conn, card_id) is not None
        conn.close()

        # Re-open and verify persistence
        conn2 = init_db(db_file)
        assert get_schema_version(conn2) == 2
        assert get_card(conn2, card_id) is not None


# ---------------------------------------------------------------------------
# TestV1Migration
# ---------------------------------------------------------------------------

class TestV1Migration:
    def test_v1_migrates_to_v2(self):
        """A v1 database is upgraded to v2: columns gone, low stability floored."""
        conn = _create_v1_db()

        # Insert a card with low stability and v1-only fields
        with conn:
            conn.execute("""
                INSERT INTO cards
                    (deck, indicator_id, entity, era, question, answer,
                     state, consecutive_successes, stability)
                VALUES ('test', 'IND001', 'World', '2020s', 'Q?', 42.0,
                        'learning', 2, 0.3)
            """)
            card_id = conn.execute(
                "SELECT card_id FROM cards WHERE indicator_id='IND001'"
            ).fetchone()[0]

        # Run the migration
        _migrate(conn)

        assert get_schema_version(conn) == 2

        # Verify removed columns are gone
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        assert "state" not in cols
        assert "consecutive_successes" not in cols

        # Verify stability was floored to 0.5
        row = conn.execute(
            "SELECT stability FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(0.5)

    def test_v1_migration_preserves_high_stability(self):
        """Cards with stability > 0.5 keep their stability unchanged."""
        conn = _create_v1_db()

        with conn:
            conn.execute("""
                INSERT INTO cards
                    (deck, indicator_id, entity, era, question, answer,
                     state, consecutive_successes, stability)
                VALUES ('test', 'IND001', 'World', '2020s', 'Q?', 42.0,
                        'review', 3, 7.5)
            """)
            card_id = conn.execute(
                "SELECT card_id FROM cards WHERE indicator_id='IND001'"
            ).fetchone()[0]

        _migrate(conn)

        row = conn.execute(
            "SELECT stability FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(7.5)

    def test_v1_migration_preserves_reviews(self):
        """review_log entries survive the v1→v2 migration."""
        conn = _create_v1_db()

        with conn:
            conn.execute("""
                INSERT INTO cards
                    (deck, indicator_id, entity, era, question, answer)
                VALUES ('test', 'IND001', 'World', '2020s', 'Q?', 42.0)
            """)
            card_id = conn.execute(
                "SELECT card_id FROM cards WHERE indicator_id='IND001'"
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO review_log
                    (card_id, timestamp, answer_mode, user_lower, user_upper,
                     user_point, true_answer, raw_score, desired_retention,
                     interval_applied, elapsed_days)
                VALUES (?, '2025-01-01T12:00:00', 'interval', 30.0, 50.0,
                        NULL, 42.0, 0.75, 0.90, 3.0, 0.0)
            """, (card_id,))

        _migrate(conn)

        reviews = conn.execute(
            "SELECT * FROM review_log WHERE card_id = ?", (card_id,)
        ).fetchall()
        assert len(reviews) == 1
        assert reviews[0]["raw_score"] == pytest.approx(0.75)
