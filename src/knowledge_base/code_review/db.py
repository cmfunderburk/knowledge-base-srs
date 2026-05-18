import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[3]
DB_PATH = _REPO_ROOT / "data" / "code_exercises.db"
EXERCISES_DIR = _REPO_ROOT / "exercises"

_DDL_EXERCISES = """
CREATE TABLE IF NOT EXISTS code_exercises (
    exercise_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT    NOT NULL UNIQUE,
    title         TEXT    NOT NULL,
    path          TEXT    NOT NULL DEFAULT '',
    source        TEXT    NOT NULL DEFAULT '',
    phase         INTEGER NOT NULL DEFAULT 1,
    step_index    INTEGER NOT NULL DEFAULT 0,
    stability     REAL    NOT NULL DEFAULT 0.0,
    difficulty    REAL    NOT NULL DEFAULT 0.0,
    last_review   TEXT,
    due           TEXT,
    reps          INTEGER NOT NULL DEFAULT 0,
    added         TEXT    NOT NULL
);
"""

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS code_review_log (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id      INTEGER NOT NULL REFERENCES code_exercises(exercise_id),
    timestamp        TEXT    NOT NULL,
    grade            INTEGER NOT NULL,
    prior_phase      INTEGER NOT NULL,
    new_phase        INTEGER NOT NULL,
    prior_stability  REAL    NOT NULL,
    new_stability    REAL    NOT NULL,
    prior_difficulty REAL    NOT NULL,
    new_difficulty   REAL    NOT NULL,
    elapsed_days     REAL    NOT NULL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_code_exercises_due  ON code_exercises (due);
CREATE INDEX IF NOT EXISTS idx_code_review_log_eid ON code_review_log (exercise_id);
"""

LAST_MIGRATION_PURGE: list[str] = []


def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    global LAST_MIGRATION_PURGE
    LAST_MIGRATION_PURGE = []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Detect old box-column schema and drop both tables if present
    with conn:
        existing_tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('code_exercises','code_review_log')"
            ).fetchall()
        }
        if "code_exercises" in existing_tables:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(code_exercises)").fetchall()}
            if "box" in cols:
                purged = [
                    row[0] for row in conn.execute(
                        "SELECT slug FROM code_exercises"
                    ).fetchall()
                ]
                conn.execute("DROP TABLE IF EXISTS code_review_log")
                conn.execute("DROP TABLE IF EXISTS code_exercises")
                LAST_MIGRATION_PURGE = purged

        conn.execute(_DDL_EXERCISES)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)

    return conn


def add_exercise(
    conn: sqlite3.Connection,
    slug: str,
    title: str,
    path: str,
    source: str = "",
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO code_exercises (slug, title, path, source, added) VALUES (?, ?, ?, ?, ?)",
        (slug, title, path, source, now),
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


def _extract_title(problem_md: Path) -> str:
    for line in problem_md.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return problem_md.parent.name


def discover_exercises(exercises_dir: str | Path) -> list[tuple[str, str, str]]:
    """Walk `exercises_dir` and yield (slug, title, rel_path) for every directory
    containing problem.md, test_solution.py, and solution.py.

    Returns results sorted by rel_path for deterministic ordering.
    """
    root = Path(exercises_dir).resolve()
    if not root.is_dir():
        return []
    found: list[tuple[str, str, str]] = []
    for problem_md in root.rglob("problem.md"):
        d = problem_md.parent
        if not (d / "test_solution.py").exists():
            continue
        if not (d / "solution.py").exists():
            continue
        found.append((d.name, _extract_title(problem_md), str(d.relative_to(root))))
    found.sort(key=lambda t: t[2])
    return found


def sync_exercises_from_disk(
    conn: sqlite3.Connection, exercises_dir: str | Path
) -> list[str]:
    """Register any on-disk exercises not yet in the DB. Returns slugs added.

    Existing rows (and their scheduling state) are left untouched. Slug collisions
    across directories — first-seen wins, later duplicates are silently skipped.
    """
    now = datetime.now(timezone.utc).isoformat()
    existing = {
        row[0] for row in conn.execute("SELECT slug FROM code_exercises").fetchall()
    }
    added: list[str] = []
    with conn:
        for slug, title, rel_path in discover_exercises(exercises_dir):
            if slug in existing:
                continue
            try:
                conn.execute(
                    "INSERT INTO code_exercises (slug, title, path, source, added) "
                    "VALUES (?, ?, ?, '', ?)",
                    (slug, title, rel_path, now),
                )
                added.append(slug)
                existing.add(slug)
            except sqlite3.IntegrityError:
                pass
    return added


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
