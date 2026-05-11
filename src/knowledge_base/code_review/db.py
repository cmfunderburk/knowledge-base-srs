import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[3]
DB_PATH = _REPO_ROOT / "data" / "code_exercises.db"

_DDL_EXERCISES = """
CREATE TABLE IF NOT EXISTS code_exercises (
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

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS code_review_log (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id  INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
    timestamp    TEXT    NOT NULL,
    grade        INTEGER NOT NULL,
    prior_box    INTEGER NOT NULL,
    new_box      INTEGER NOT NULL,
    elapsed_days REAL    NOT NULL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_code_exercises_due  ON code_exercises (due);
CREATE INDEX IF NOT EXISTS idx_code_review_log_eid ON code_review_log (exercise_id);
"""


def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    with conn:
        conn.execute(_DDL_EXERCISES)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
    return conn


def add_exercise(
    conn: sqlite3.Connection, slug: str, title: str, source: str = ""
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO code_exercises (slug, title, source, added) VALUES (?, ?, ?, ?)",
        (slug, title, source, now),
    )
    conn.commit()
    return cur.lastrowid


def get_exercise_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM code_exercises WHERE slug = ?", (slug,)
    ).fetchone()
    return dict(row) if row else None


def get_due_exercises(conn: sqlite3.Connection, as_of: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM code_exercises WHERE due IS NULL OR due <= ? ORDER BY due ASC NULLS FIRST",
        (as_of,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_exercise_scheduling(
    conn: sqlite3.Connection, exercise_id: int, box: int, due: str, now: str
) -> None:
    cur = conn.execute(
        "UPDATE code_exercises SET box=?, due=?, last_review=?, reps=reps+1 WHERE exercise_id=?",
        (box, due, now, exercise_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError(f"No exercise with exercise_id={exercise_id}")


_REVIEW_LOG_COLS = ("exercise_id", "timestamp", "grade", "prior_box", "new_box", "elapsed_days")


def insert_review_log(conn: sqlite3.Connection, review: dict) -> int:
    unknown = set(review) - set(_REVIEW_LOG_COLS)
    if unknown:
        raise ValueError(f"Unknown review_log columns: {unknown}")
    cols = [c for c in _REVIEW_LOG_COLS if c in review]
    cur = conn.execute(
        f"INSERT INTO code_review_log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [review[c] for c in cols],
    )
    conn.commit()
    return cur.lastrowid


def get_all_exercises(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM code_exercises ORDER BY slug ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def reset_exercise(conn: sqlite3.Connection, exercise_id: int) -> None:
    conn.execute(
        "UPDATE code_exercises SET box=1, reps=0, last_review=NULL, due=NULL WHERE exercise_id=?",
        (exercise_id,),
    )
    conn.commit()


def reset_all_exercises(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE code_exercises SET box=1, reps=0, last_review=NULL, due=NULL")
    conn.commit()


def record_grade(
    conn: sqlite3.Connection,
    exercise_id: int,
    box: int,
    due: str,
    now: str,
    review: dict,
) -> None:
    """Update scheduling and insert review log atomically."""
    unknown = set(review) - set(_REVIEW_LOG_COLS)
    if unknown:
        raise ValueError(f"Unknown review_log columns: {unknown}")
    cols = [c for c in _REVIEW_LOG_COLS if c in review]
    with conn:
        conn.execute(
            "UPDATE code_exercises SET box=?, due=?, last_review=?, reps=reps+1 WHERE exercise_id=?",
            (box, due, now, exercise_id),
        )
        conn.execute(
            f"INSERT INTO code_review_log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [review[c] for c in cols],
        )
