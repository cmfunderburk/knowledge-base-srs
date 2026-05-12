from datetime import datetime, timezone
import sqlite3 as _sqlite3

import pytest

from knowledge_base.code_review.db import (
    add_exercise,
    get_due_exercises,
    get_exercise_by_slug,
    init_db,
    insert_review_log,
    update_exercise_scheduling,
)


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


def test_add_exercise_returns_id(conn):
    eid = add_exercise(conn, "my-slug", "My Title", path="my-slug", source="quantecon")
    assert isinstance(eid, int)
    assert eid > 0


def test_get_exercise_by_slug(conn):
    add_exercise(conn, "slug-a", "Title A", path="slug-a")
    ex = get_exercise_by_slug(conn, "slug-a")
    assert ex is not None
    assert ex["title"] == "Title A"
    assert ex["box"] == 1
    assert ex["reps"] == 0


def test_get_exercise_by_slug_missing_returns_none(conn):
    assert get_exercise_by_slug(conn, "no-such-slug") is None


def test_get_due_exercises_includes_null_due(conn):
    add_exercise(conn, "new-exercise", "New", path="new-exercise")
    now = datetime.now(timezone.utc).isoformat()
    due = get_due_exercises(conn, now)
    assert any(e["slug"] == "new-exercise" for e in due)


def test_get_due_exercises_excludes_future(conn):
    eid = add_exercise(conn, "future-ex", "Future", path="future-ex")
    update_exercise_scheduling(conn, eid, box=3, due="2099-01-01T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    as_of = "2026-06-01T00:00:00+00:00"
    due = get_due_exercises(conn, as_of)
    assert not any(e["slug"] == "future-ex" for e in due)


def test_update_exercise_scheduling_increments_reps(conn):
    eid = add_exercise(conn, "rep-test", "Rep Test", path="rep-test")
    update_exercise_scheduling(conn, eid, box=2, due="2026-01-03T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    ex = get_exercise_by_slug(conn, "rep-test")
    assert ex["reps"] == 1
    assert ex["box"] == 2


def test_insert_review_log(conn):
    eid = add_exercise(conn, "log-test", "Log Test", path="log-test")
    review_id = insert_review_log(conn, {
        "exercise_id": eid,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "grade": 3,
        "prior_box": 1,
        "new_box": 2,
        "elapsed_days": 0.0,
    })
    assert review_id > 0


def test_foreign_key_constraint_enforced(conn):
    with pytest.raises(_sqlite3.IntegrityError):
        insert_review_log(conn, {
            "exercise_id": 9999,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "grade": 3,
            "prior_box": 1,
            "new_box": 2,
            "elapsed_days": 0.0,
        })


def test_add_exercise_persists_path(conn):
    eid = add_exercise(
        conn,
        slug="quantecon-3-1",
        title="Title",
        path="quantecon/python-programming/quantecon-3-1",
        source="quantecon-python",
    )
    ex = get_exercise_by_slug(conn, "quantecon-3-1")
    assert ex["path"] == "quantecon/python-programming/quantecon-3-1"
    assert ex["source"] == "quantecon-python"


def test_init_db_adds_path_column_to_legacy_schema(tmp_path):
    """Pre-migration DB has no `path` column; init_db must add it and purge rows lacking a path."""
    import sqlite3
    from knowledge_base.code_review import db as db_mod

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE code_exercises (
            exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         TEXT    NOT NULL UNIQUE,
            title        TEXT    NOT NULL,
            source       TEXT    NOT NULL DEFAULT '',
            box          INTEGER NOT NULL DEFAULT 1,
            last_review  TEXT,
            due          TEXT,
            reps         INTEGER NOT NULL DEFAULT 0,
            added        TEXT    NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO code_exercises (slug, title, added) VALUES (?, ?, ?)",
        ("legacy-slug", "Legacy", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    migrated = db_mod.init_db(db_path)
    cols = {row[1] for row in migrated.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "path" in cols
    rows = migrated.execute("SELECT slug FROM code_exercises").fetchall()
    assert rows == []  # legacy row purged because path was unknown
    assert db_mod.LAST_MIGRATION_PURGE == ["legacy-slug"]


def test_init_db_fresh_has_path_column(tmp_path):
    from knowledge_base.code_review import db as db_mod

    conn = db_mod.init_db(tmp_path / "fresh.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
    assert "path" in cols
    assert db_mod.LAST_MIGRATION_PURGE == []


def test_init_db_cascades_purge_to_review_log(tmp_path):
    """Pre-migration exercise with review_log rows must be purged together (no FK violation)."""
    import sqlite3
    from knowledge_base.code_review import db as db_mod

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(
        """
        CREATE TABLE code_exercises (
            exercise_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug         TEXT    NOT NULL UNIQUE,
            title        TEXT    NOT NULL,
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
        "INSERT INTO code_exercises (slug, title, added) VALUES (?, ?, ?)",
        ("legacy-slug", "Legacy", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO code_review_log "
        "(exercise_id, timestamp, grade, prior_box, new_box, elapsed_days) "
        "VALUES (1, '2026-01-02T00:00:00+00:00', 3, 1, 2, 1.0)"
    )
    conn.commit()
    conn.close()

    migrated = db_mod.init_db(db_path)
    assert migrated.execute("SELECT COUNT(*) FROM code_exercises").fetchone()[0] == 0
    assert migrated.execute("SELECT COUNT(*) FROM code_review_log").fetchone()[0] == 0
    assert db_mod.LAST_MIGRATION_PURGE == ["legacy-slug"]
