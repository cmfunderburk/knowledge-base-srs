from datetime import datetime, timezone
import sqlite3 as _sqlite3

import pytest

from knowledge_base.code_review.db import (
    add_exercise,
    get_due_exercises,
    get_exercise_by_slug,
    init_db,
)


NOW_ISO = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    return init_db(tmp_path / "test.db")


def test_init_db_creates_tables(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "code_exercises" in tables
    assert "code_review_log" in tables


def test_new_schema_has_fsrs_columns(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert {"phase", "step_index", "stability", "difficulty"} <= cols
    assert "box" not in cols

    log_cols = {row[1] for row in conn.execute("PRAGMA table_info(code_review_log)").fetchall()}
    assert {"prior_phase", "new_phase", "prior_stability", "new_stability",
            "prior_difficulty", "new_difficulty"} <= log_cols
    assert "prior_box" not in log_cols
    assert "new_box" not in log_cols


def test_add_exercise_defaults_to_learning_phase(conn):
    eid = add_exercise(conn, "slug-a", "Title A", path="slug-a")
    ex = get_exercise_by_slug(conn, "slug-a")
    assert ex["phase"] == 1  # Phase.LEARNING
    assert ex["step_index"] == 0
    assert ex["stability"] == 0.0
    assert ex["difficulty"] == 0.0
    assert ex["reps"] == 0


def test_get_exercise_by_slug_missing_returns_none(conn):
    assert get_exercise_by_slug(conn, "no-such-slug") is None


def test_get_due_exercises_includes_null_due(conn):
    add_exercise(conn, "new-exercise", "New", path="new-exercise")
    due = get_due_exercises(conn, NOW_ISO)
    assert any(e["slug"] == "new-exercise" for e in due)


def test_get_due_exercises_excludes_future(conn):
    """Caller passes its own learn-ahead-adjusted timestamp; the DB just compares against `due`."""
    eid = add_exercise(conn, "future-ex", "Future", path="future-ex")
    # Manually set a far-future due
    conn.execute(
        "UPDATE code_exercises SET phase=2, due=? WHERE exercise_id=?",
        ("2099-01-01T00:00:00+00:00", eid),
    )
    conn.commit()
    due = get_due_exercises(conn, "2026-06-01T00:00:00+00:00")
    assert not any(e["slug"] == "future-ex" for e in due)


def test_migration_drops_old_box_schema(tmp_path):
    """A DB created with the legacy `box`-column schema is wiped on init_db."""
    from knowledge_base.code_review import db as db_mod

    db_path = tmp_path / "legacy.db"
    conn = _sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(
        """
        CREATE TABLE code_exercises (
            exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         TEXT    NOT NULL UNIQUE,
            title        TEXT    NOT NULL,
            path         TEXT    NOT NULL DEFAULT '',
            source       TEXT    NOT NULL DEFAULT '',
            box          INTEGER NOT NULL DEFAULT 1,
            last_review  TEXT,
            due          TEXT,
            reps         INTEGER NOT NULL DEFAULT 0,
            added        TEXT    NOT NULL
        );
        CREATE TABLE code_review_log (
            review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id  INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
            timestamp    TEXT    NOT NULL,
            grade        INTEGER NOT NULL,
            prior_box    INTEGER NOT NULL,
            new_box      INTEGER NOT NULL,
            elapsed_days REAL    NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO code_exercises (slug, title, path, added) "
        "VALUES (?, ?, ?, ?)",
        ("legacy-slug", "Legacy Title", "legacy-slug", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO code_review_log "
        "(exercise_id, timestamp, grade, prior_box, new_box, elapsed_days) "
        "VALUES (1, '2026-01-02T00:00:00+00:00', 3, 1, 2, 1.0)"
    )
    conn.commit()
    conn.close()

    migrated = db_mod.init_db(db_path)
    cols = {row[1] for row in migrated.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "phase" in cols
    assert "box" not in cols
    assert migrated.execute("SELECT COUNT(*) FROM code_exercises").fetchone()[0] == 0
    assert migrated.execute("SELECT COUNT(*) FROM code_review_log").fetchone()[0] == 0
    assert db_mod.LAST_MIGRATION_PURGE == ["legacy-slug"]


def test_init_db_fresh_no_migration_purge(tmp_path):
    from knowledge_base.code_review import db as db_mod
    db_mod.init_db(tmp_path / "fresh.db")
    assert db_mod.LAST_MIGRATION_PURGE == []


from knowledge_base.code_review.db import record_grade, reset_exercise, reset_all_exercises, get_all_exercises


def _make_review_state(prior, new):
    """Build a record_grade payload from before/after dicts."""
    return {
        "exercise_id": prior["exercise_id"],
        "prior_phase": prior["phase"],
        "new_phase": new["phase"],
        "prior_stability": prior["stability"],
        "new_stability": new["stability"],
        "prior_difficulty": prior["difficulty"],
        "new_difficulty": new["difficulty"],
        "grade": 3,
        "elapsed_days": 1.0,
    }


def test_record_grade_writes_both_tables_atomically(conn):
    eid = add_exercise(conn, "rg", "RG", path="rg")
    prior = get_exercise_by_slug(conn, "rg")
    new = {
        "phase": 1, "step_index": 1, "stability": 0.0, "difficulty": 0.0,
        "reps": 1, "last_review": NOW_ISO, "due": "2026-01-01T00:10:00+00:00",
    }
    review = _make_review_state(prior, {**new, "phase": 1, "stability": 0.0, "difficulty": 0.0})
    record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    after = get_exercise_by_slug(conn, "rg")
    assert after["phase"] == 1
    assert after["step_index"] == 1
    assert after["due"] == "2026-01-01T00:10:00+00:00"
    assert after["last_review"] == NOW_ISO
    assert after["reps"] == 1

    logs = conn.execute("SELECT * FROM code_review_log WHERE exercise_id=?", (eid,)).fetchall()
    assert len(logs) == 1
    assert logs[0]["grade"] == 3


def test_record_grade_atomicity_on_bad_review_dict(conn):
    """A bad review payload rolls back both writes."""
    eid = add_exercise(conn, "atom", "Atom", path="atom")
    new = {
        "phase": 2, "step_index": 0, "stability": 3.0, "difficulty": 5.0,
        "reps": 1, "last_review": NOW_ISO, "due": "2026-01-04T00:00:00+00:00",
    }
    review = {"exercise_id": eid, "bogus_column": 1}
    with pytest.raises(ValueError):
        record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    after = get_exercise_by_slug(conn, "atom")
    # Should still be in initial state
    assert after["phase"] == 1
    assert after["reps"] == 0
    assert conn.execute("SELECT COUNT(*) FROM code_review_log").fetchone()[0] == 0


def test_reset_exercise_clears_state(conn):
    eid = add_exercise(conn, "rst", "Reset", path="rst")
    new = {
        "phase": 2, "step_index": 0, "stability": 5.0, "difficulty": 6.0,
        "reps": 3, "last_review": NOW_ISO, "due": "2026-02-01T00:00:00+00:00",
    }
    prior = get_exercise_by_slug(conn, "rst")
    review = _make_review_state(prior, new)
    record_grade(conn, exercise_id=eid, new_state=new, review=review, now=NOW_ISO)

    reset_exercise(conn, eid)
    after = get_exercise_by_slug(conn, "rst")
    assert after["phase"] == 1
    assert after["step_index"] == 0
    assert after["stability"] == 0.0
    assert after["difficulty"] == 0.0
    assert after["reps"] == 0
    assert after["last_review"] is None
    assert after["due"] is None


def test_reset_all_exercises_resets_every_row(conn):
    add_exercise(conn, "a", "A", path="a")
    add_exercise(conn, "b", "B", path="b")
    reset_all_exercises(conn)
    for ex in get_all_exercises(conn):
        assert ex["phase"] == 1
        assert ex["reps"] == 0
