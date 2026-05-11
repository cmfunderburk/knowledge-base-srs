from datetime import datetime, timezone

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
    eid = add_exercise(conn, "my-slug", "My Title", "quantecon")
    assert isinstance(eid, int)
    assert eid > 0


def test_get_exercise_by_slug(conn):
    add_exercise(conn, "slug-a", "Title A")
    ex = get_exercise_by_slug(conn, "slug-a")
    assert ex is not None
    assert ex["title"] == "Title A"
    assert ex["box"] == 1
    assert ex["reps"] == 0


def test_get_exercise_by_slug_missing_returns_none(conn):
    assert get_exercise_by_slug(conn, "no-such-slug") is None


def test_get_due_exercises_includes_null_due(conn):
    add_exercise(conn, "new-exercise", "New")
    now = datetime.now(timezone.utc).isoformat()
    due = get_due_exercises(conn, now)
    assert any(e["slug"] == "new-exercise" for e in due)


def test_get_due_exercises_excludes_future(conn):
    eid = add_exercise(conn, "future-ex", "Future")
    update_exercise_scheduling(conn, eid, box=3, due="2099-01-01T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    as_of = "2026-06-01T00:00:00+00:00"
    due = get_due_exercises(conn, as_of)
    assert not any(e["slug"] == "future-ex" for e in due)


def test_update_exercise_scheduling_increments_reps(conn):
    eid = add_exercise(conn, "rep-test", "Rep Test")
    update_exercise_scheduling(conn, eid, box=2, due="2026-01-03T00:00:00+00:00", now="2026-01-01T00:00:00+00:00")
    ex = get_exercise_by_slug(conn, "rep-test")
    assert ex["reps"] == 1
    assert ex["box"] == 2


def test_insert_review_log(conn):
    eid = add_exercise(conn, "log-test", "Log Test")
    review_id = insert_review_log(conn, {
        "exercise_id": eid,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "grade": 3,
        "prior_box": 1,
        "new_box": 2,
        "elapsed_days": 0.0,
    })
    assert review_id > 0
