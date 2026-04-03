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
    get_cards_by_readings,
    get_cards_by_source,
    get_catalog_tree,
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
        "source": "los",
        "topic_id": "1",
        "section_id": "1.a",
        "card_index": 0,
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
        assert CURRENT_SCHEMA_VERSION == 2

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
        assert "idx_gen_cards_source" in index_names
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
        assert retrieved["section_id"] == "1.a"
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
        gen_id = insert_generation_card(conn, _minimal_card(section_id="1.a"))
        # Insert a recall-phase card
        recall_id = insert_generation_card(conn, _minimal_card(section_id="1.b"))
        update_generation_phase(conn, recall_id, {"phase": "recall"})

        results = get_generation_phase_cards(conn)
        result_ids = [r["card_id"] for r in results]
        assert gen_id in result_ids
        assert recall_id not in result_ids

    def test_generation_phase_cards_deck_filter(self):
        conn = init_generation_db()
        id_a = insert_generation_card(conn, _minimal_card(deck="deck_a", section_id="1.a"))
        id_b = insert_generation_card(conn, _minimal_card(deck="deck_b", section_id="1.b"))

        results_a = get_generation_phase_cards(conn, deck="deck_a")
        assert len(results_a) == 1
        assert results_a[0]["card_id"] == id_a

        results_b = get_generation_phase_cards(conn, deck="deck_b")
        assert len(results_b) == 1
        assert results_b[0]["card_id"] == id_b

    def test_generation_phase_cards_limit(self):
        conn = init_generation_db()
        for i in range(5):
            insert_generation_card(conn, _minimal_card(section_id=f"1.{i}"))

        results = get_generation_phase_cards(conn, limit=3)
        assert len(results) == 3

    def test_generation_phase_cards_random_order(self):
        """Generation-phase cards should be returned in random order."""
        conn = init_generation_db()
        for i in range(20):
            insert_generation_card(conn, _minimal_card(section_id=f"los_{i}"))

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

        id_older = insert_generation_card(conn, _minimal_card(section_id="1.a"))
        update_generation_phase(conn, id_older, {"phase": "recall"})
        update_generation_scheduling(conn, id_older, {
            "reps": 1,
            "due": "2025-01-01T00:00:00",
        })

        id_newer = insert_generation_card(conn, _minimal_card(section_id="1.b"))
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

        id_a = insert_generation_card(conn, _minimal_card(deck="deck_a", section_id="1.a"))
        update_generation_phase(conn, id_a, {"phase": "recall"})
        update_generation_scheduling(conn, id_a, {"reps": 1, "due": "2026-01-01T00:00:00"})

        id_b = insert_generation_card(conn, _minimal_card(deck="deck_b", section_id="1.b"))
        update_generation_phase(conn, id_b, {"phase": "recall"})
        update_generation_scheduling(conn, id_b, {"reps": 1, "due": "2026-01-01T00:00:00"})

        results_a = get_due_generation_cards(conn, as_of="2026-06-01T00:00:00", deck="deck_a")
        assert len(results_a) == 1
        assert results_a[0]["card_id"] == id_a

    def test_due_generation_cards_limit(self):
        conn = init_generation_db()
        for i in range(5):
            cid = insert_generation_card(conn, _minimal_card(section_id=f"los_{i}"))
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



# ---------------------------------------------------------------------------
# TestSchemaV2Migration
# ---------------------------------------------------------------------------


def _create_v1_db(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Create a v1 schema database directly (bypassing init_generation_db).

    Returns the connection with v1 tables set up and version stamped as 1.
    """
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_schema_version (
            version INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_cards (
            card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
            deck                   TEXT    NOT NULL,
            topic_id               TEXT    NOT NULL,
            los_id                 TEXT    NOT NULL,
            question               TEXT    NOT NULL,
            answer                 TEXT    NOT NULL,
            tags                   TEXT    NOT NULL DEFAULT '[]',
            masking_level          INTEGER NOT NULL DEFAULT 0,
            phase                  TEXT    NOT NULL DEFAULT 'generation',
            consecutive_max_passes INTEGER NOT NULL DEFAULT 0,
            difficulty             REAL    NOT NULL DEFAULT 5.0,
            stability              REAL    NOT NULL DEFAULT 0.0,
            last_review            TEXT,
            due                    TEXT,
            reps                   INTEGER NOT NULL DEFAULT 0,
            UNIQUE (deck, los_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_review_log (
            review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id          INTEGER NOT NULL REFERENCES generation_cards(card_id),
            timestamp        TEXT    NOT NULL,
            answer_mode      TEXT    NOT NULL,
            phase_level      INTEGER,
            grade            INTEGER,
            passed           INTEGER,
            elapsed_days     REAL    NOT NULL,
            interval_applied REAL
        )
    """)
    conn.execute("INSERT INTO generation_schema_version (version) VALUES (1)")
    conn.commit()
    return conn


class TestSchemaV2Migration:
    """Tests for v1 → v2 migration (los_id → section_id, new columns)."""

    def test_migration_runs_on_v1_db(self):
        """init_generation_db on a v1 database migrates to v2."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        # Insert a v1 card
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()

        # Now run init, which should detect v1 and migrate
        init_generation_db(conn=conn)

        version = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()[0]
        assert version == 2

    def test_migration_renames_los_id_to_section_id(self):
        """After migration, los_id column is gone and section_id exists."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()

        init_generation_db(conn=conn)

        # section_id should exist with old los_id value
        row = conn.execute(
            "SELECT section_id FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert row is not None
        assert row["section_id"] == "1.a"

        # los_id column should not exist
        cols = {
            info[1]
            for info in conn.execute("PRAGMA table_info(generation_cards)").fetchall()
        }
        assert "section_id" in cols
        assert "los_id" not in cols

    def test_migration_adds_source_column(self):
        """Migrated cards get source='los'."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()

        init_generation_db(conn=conn)

        row = conn.execute(
            "SELECT source FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert row["source"] == "los"

    def test_migration_adds_card_index_column(self):
        """Migrated cards get card_index=0."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()

        init_generation_db(conn=conn)

        row = conn.execute(
            "SELECT card_index FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert row["card_index"] == 0

    def test_migration_adds_section_title_column(self):
        """Migrated cards get section_title=NULL."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()

        init_generation_db(conn=conn)

        row = conn.execute(
            "SELECT section_title FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert row["section_title"] is None

    def test_migration_preserves_scheduling_state(self):
        """Scheduling fields (difficulty, stability, reps, due, last_review) survive migration."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards "
            "(deck, topic_id, los_id, question, answer, difficulty, stability, "
            " reps, due, last_review) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.', 3.5, 7.5, 5, "
            " '2026-01-08T00:00:00', '2026-01-01T00:00:00')"
        )
        conn.commit()

        init_generation_db(conn=conn)

        row = conn.execute(
            "SELECT * FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        row = dict(row)
        assert row["difficulty"] == pytest.approx(3.5)
        assert row["stability"] == pytest.approx(7.5)
        assert row["reps"] == 5
        assert row["due"] == "2026-01-08T00:00:00"
        assert row["last_review"] == "2026-01-01T00:00:00"

    def test_migration_preserves_phase_state(self):
        """Phase fields (phase, masking_level, consecutive_max_passes) survive migration."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards "
            "(deck, topic_id, los_id, question, answer, "
            " phase, masking_level, consecutive_max_passes) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.', 'recall', 2, 3)"
        )
        conn.commit()

        init_generation_db(conn=conn)

        row = conn.execute(
            "SELECT * FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        row = dict(row)
        assert row["phase"] == "recall"
        assert row["masking_level"] == 2
        assert row["consecutive_max_passes"] == 3

    def test_migration_preserves_card_id(self):
        """card_id values are preserved across migration."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        conn.commit()
        original_id = conn.execute(
            "SELECT card_id FROM generation_cards WHERE los_id = '1.a'"
        ).fetchone()[0]

        init_generation_db(conn=conn)

        migrated_id = conn.execute(
            "SELECT card_id FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()[0]
        assert migrated_id == original_id

    def test_migration_preserves_review_log(self):
        """Review log entries with foreign keys survive migration."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.')"
        )
        card_id = conn.execute(
            "SELECT card_id FROM generation_cards WHERE los_id = '1.a'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO generation_review_log "
            "(card_id, timestamp, answer_mode, phase_level, grade, passed, "
            " elapsed_days, interval_applied) "
            "VALUES (?, '2026-01-01T12:00:00', 'generation', 0, NULL, 1, 0.0, NULL)",
            (card_id,),
        )
        conn.commit()

        init_generation_db(conn=conn)

        count = conn.execute(
            "SELECT COUNT(*) FROM generation_review_log WHERE card_id = ?",
            (card_id,),
        ).fetchone()[0]
        assert count == 1

    def test_migration_multiple_cards(self):
        """Migration handles multiple cards correctly."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        for i, lid in enumerate(["1.a", "1.b", "2.a"]):
            conn.execute(
                "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer) "
                "VALUES ('cfa', ?, ?, ?, ?)",
                (str(i + 1), lid, f"Q{lid}?", f"A{lid}."),
            )
        conn.commit()

        init_generation_db(conn=conn)

        count = conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        assert count == 3

        for lid in ["1.a", "1.b", "2.a"]:
            row = conn.execute(
                "SELECT section_id, source, card_index FROM generation_cards "
                "WHERE section_id = ?", (lid,)
            ).fetchone()
            assert row is not None
            assert row["source"] == "los"
            assert row["card_index"] == 0

    def test_migration_new_unique_constraint(self):
        """After migration, the unique constraint is (deck, source, topic_id, section_id, card_index)."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        init_generation_db(conn=conn)

        # Insert two cards that would have conflicted under old constraint
        # but are distinct under new constraint (different source)
        insert_generation_card(conn, _minimal_card(
            section_id="1.a", source="los", card_index=0,
        ))
        insert_generation_card(conn, _minimal_card(
            section_id="1.a", source="overview", card_index=0,
        ))
        count = conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        assert count == 2

    def test_v2_db_no_migration_needed(self):
        """init_generation_db on an already-v2 database is a no-op."""
        conn = init_generation_db()  # Creates a fresh v2 DB
        insert_generation_card(conn, _minimal_card())

        # Re-init should not break anything
        init_generation_db(conn=conn)

        version = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()[0]
        assert version == 2

        card = conn.execute(
            "SELECT * FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert card is not None

    def test_migration_file_based(self, tmp_path):
        """Migration works on a file-based database."""
        db_file = tmp_path / "migrate_test.db"
        conn = _create_v1_db(sqlite3.connect(str(db_file)))
        conn.execute(
            "INSERT INTO generation_cards (deck, topic_id, los_id, question, answer, "
            "difficulty, stability, reps, phase, masking_level) "
            "VALUES ('cfa', '1', '1.a', 'Q?', 'A.', 4.0, 10.0, 3, 'recall', 2)"
        )
        conn.commit()
        conn.close()

        # Re-open with init — should trigger migration
        conn2 = init_generation_db(db_path=str(db_file))
        version = conn2.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()[0]
        assert version == 2


# ---------------------------------------------------------------------------
# TestSourceSectionQueries
# ---------------------------------------------------------------------------


class TestSourceSectionQueries:
    """Tests for get_cards_by_source and get_catalog_tree."""

    def _populate(self, conn) -> dict:
        """Insert cards across multiple sources and sections.

        Returns a dict mapping descriptive keys to card_ids so tests can
        make precise assertions.
        """
        cards = {
            # deck=cfa_level1, source=los, topic_id=1, section_id=1.a
            "los_t1_1a_i0": insert_generation_card(conn, _minimal_card(
                deck="cfa_level1", source="los", topic_id="1",
                section_id="1.a", card_index=0,
                question="LOS T1 1.a card 0?", answer="A",
            )),
            # deck=cfa_level1, source=los, topic_id=1, section_id=1.b
            "los_t1_1b_i0": insert_generation_card(conn, _minimal_card(
                deck="cfa_level1", source="los", topic_id="1",
                section_id="1.b", card_index=0,
                question="LOS T1 1.b card 0?", answer="B",
            )),
            # deck=cfa_level1, source=los, topic_id=2, section_id=2.a
            "los_t2_2a_i0": insert_generation_card(conn, _minimal_card(
                deck="cfa_level1", source="los", topic_id="2",
                section_id="2.a", card_index=0,
                question="LOS T2 2.a card 0?", answer="C",
            )),
            # deck=cfa_level1, source=markdown, topic_id=1, section_id=1.a, card_index=0
            "md_t1_1a_i0": insert_generation_card(conn, _minimal_card(
                deck="cfa_level1", source="markdown", topic_id="1",
                section_id="1.a", card_index=0,
                question="Markdown T1 1.a card 0?", answer="D",
            )),
            # deck=cfa_level1, source=markdown, topic_id=1, section_id=1.a, card_index=1
            "md_t1_1a_i1": insert_generation_card(conn, _minimal_card(
                deck="cfa_level1", source="markdown", topic_id="1",
                section_id="1.a", card_index=1,
                question="Markdown T1 1.a card 1?", answer="E",
            )),
            # deck=other_deck, source=los, topic_id=1, section_id=1.a
            "other_los_t1_1a": insert_generation_card(conn, _minimal_card(
                deck="other_deck", source="los", topic_id="1",
                section_id="1.a", card_index=0,
                question="Other deck LOS T1 1.a?", answer="F",
            )),
        }
        return cards

    # --- get_cards_by_source ---

    def test_get_cards_by_source_returns_matching_source(self):
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_source(conn, source="markdown")
        result_ids = {r["card_id"] for r in results}

        assert ids["md_t1_1a_i0"] in result_ids
        assert ids["md_t1_1a_i1"] in result_ids
        assert ids["los_t1_1a_i0"] not in result_ids
        assert ids["los_t1_1b_i0"] not in result_ids

    def test_get_cards_by_source_with_topic_filter(self):
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_source(conn, source="los", topic_ids=["1"])
        result_ids = {r["card_id"] for r in results}

        # topic_id=1 cards from los, across both decks
        assert ids["los_t1_1a_i0"] in result_ids
        assert ids["los_t1_1b_i0"] in result_ids
        assert ids["other_los_t1_1a"] in result_ids
        # topic_id=2 card excluded
        assert ids["los_t2_2a_i0"] not in result_ids
        # markdown cards excluded
        assert ids["md_t1_1a_i0"] not in result_ids

    def test_get_cards_by_source_with_section_filter(self):
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_source(conn, source="los", section_ids=["1.a"])
        result_ids = {r["card_id"] for r in results}

        assert ids["los_t1_1a_i0"] in result_ids
        assert ids["other_los_t1_1a"] in result_ids
        assert ids["los_t1_1b_i0"] not in result_ids
        assert ids["los_t2_2a_i0"] not in result_ids

    def test_get_cards_by_source_with_topic_and_section_filter(self):
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_source(
            conn, source="los", topic_ids=["1"], section_ids=["1.a"]
        )
        result_ids = {r["card_id"] for r in results}

        assert ids["los_t1_1a_i0"] in result_ids
        assert ids["other_los_t1_1a"] in result_ids
        # 1.b excluded by section filter
        assert ids["los_t1_1b_i0"] not in result_ids
        # topic_id=2 excluded by topic filter
        assert ids["los_t2_2a_i0"] not in result_ids

    def test_get_cards_by_source_with_deck_filter(self):
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_source(
            conn, source="los", deck="cfa_level1"
        )
        result_ids = {r["card_id"] for r in results}

        assert ids["los_t1_1a_i0"] in result_ids
        assert ids["los_t1_1b_i0"] in result_ids
        assert ids["los_t2_2a_i0"] in result_ids
        # other_deck excluded
        assert ids["other_los_t1_1a"] not in result_ids

    def test_get_cards_by_source_returns_all_fields(self):
        conn = init_generation_db()
        self._populate(conn)

        results = get_cards_by_source(conn, source="markdown", deck="cfa_level1")
        assert len(results) == 2
        for row in results:
            assert "card_id" in row
            assert "source" in row
            assert "topic_id" in row
            assert "section_id" in row
            assert "question" in row
            assert "answer" in row

    def test_get_cards_by_source_empty_when_no_match(self):
        conn = init_generation_db()
        self._populate(conn)

        results = get_cards_by_source(conn, source="nonexistent_source")
        assert results == []

    # --- get_cards_by_readings backwards compatibility ---

    def test_get_cards_by_readings_returns_cards_from_all_sources(self):
        """get_cards_by_readings should return cards from ALL sources for given topic_ids."""
        conn = init_generation_db()
        ids = self._populate(conn)

        results = get_cards_by_readings(conn, topic_ids=["1"], deck="cfa_level1")
        result_ids = {r["card_id"] for r in results}

        # Both los and markdown cards with topic_id=1 should appear
        assert ids["los_t1_1a_i0"] in result_ids
        assert ids["los_t1_1b_i0"] in result_ids
        assert ids["md_t1_1a_i0"] in result_ids
        assert ids["md_t1_1a_i1"] in result_ids
        # topic_id=2 excluded
        assert ids["los_t2_2a_i0"] not in result_ids

    # --- get_catalog_tree ---

    def test_get_catalog_tree_grouping_and_counts(self):
        conn = init_generation_db()
        self._populate(conn)

        rows = get_catalog_tree(conn, deck="cfa_level1")

        # Build a lookup: (topic_id, source, section_id) -> card_count
        lookup = {
            (r["topic_id"], r["source"], r["section_id"]): r["card_count"]
            for r in rows
        }

        assert lookup[("1", "los", "1.a")] == 1
        assert lookup[("1", "los", "1.b")] == 1
        assert lookup[("2", "los", "2.a")] == 1
        assert lookup[("1", "markdown", "1.a")] == 2  # two markdown cards

    def test_get_catalog_tree_deck_filter_excludes_other_decks(self):
        conn = init_generation_db()
        self._populate(conn)

        rows = get_catalog_tree(conn, deck="cfa_level1")
        decks_returned = {r["deck"] for r in rows}

        assert decks_returned == {"cfa_level1"}

    def test_get_catalog_tree_without_deck_filter_returns_all_decks(self):
        conn = init_generation_db()
        self._populate(conn)

        rows = get_catalog_tree(conn)
        decks_returned = {r["deck"] for r in rows}

        assert "cfa_level1" in decks_returned
        assert "other_deck" in decks_returned

    def test_get_catalog_tree_row_keys(self):
        conn = init_generation_db()
        self._populate(conn)

        rows = get_catalog_tree(conn)
        assert len(rows) > 0
        for row in rows:
            assert "deck" in row
            assert "topic_id" in row
            assert "source" in row
            assert "section_id" in row
            assert "section_title" in row
            assert "card_count" in row

    def test_get_catalog_tree_ordered(self):
        """Rows are ordered by deck, topic_id, source, section_id."""
        conn = init_generation_db()
        self._populate(conn)

        rows = get_catalog_tree(conn, deck="cfa_level1")
        keys = [(r["topic_id"], r["source"], r["section_id"]) for r in rows]
        assert keys == sorted(keys)

    def test_get_catalog_tree_empty_db(self):
        conn = init_generation_db()
        rows = get_catalog_tree(conn)
        assert rows == []

    def test_foreign_keys_enabled_after_migration(self):
        """FK enforcement must be ON after migrating a v1 database."""
        conn = _create_v1_db(sqlite3.connect(":memory:"))
        conn = init_generation_db(conn=conn)
        fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1, "Foreign keys should be enabled after migration"

        # Verify FK enforcement actually works — inserting a review log
        # with a non-existent card_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO generation_review_log "
                "(card_id, timestamp, answer_mode, elapsed_days) "
                "VALUES (99999, '2026-01-01', 'test', 0.0)"
            )
