"""SQLite persistence layer for the SRS system.

Provides schema creation, CRUD operations, and migration support for the
cards and review_log tables used by the spaced-repetition scheduler.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 3

_DDL_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

_DDL_CARDS = """
CREATE TABLE IF NOT EXISTS cards (
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
    difficulty              REAL    NOT NULL DEFAULT 7.0,
    stability               REAL    NOT NULL DEFAULT 0.0067,
    last_review             TEXT,
    due                     TEXT,
    reps                    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (indicator_id, entity, era)
);
"""

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS review_log (
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
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_cards_due           ON cards (due, reps);
CREATE INDEX IF NOT EXISTS idx_cards_deck          ON cards (deck);
CREATE INDEX IF NOT EXISTS idx_review_log_card     ON review_log (card_id);
CREATE INDEX IF NOT EXISTS idx_review_log_timestamp ON review_log (timestamp);
"""

# ---------------------------------------------------------------------------
# Scheduling field names — used by update_card_scheduling
# ---------------------------------------------------------------------------

_SCHEDULING_FIELDS = frozenset({
    "difficulty",
    "stability",
    "last_review",
    "due",
    "reps",
})

# Content fields updated on upsert (scheduling state is preserved)
_CONTENT_FIELDS = (
    "deck",
    "question",
    "answer",
    "unit_prefix",
    "unit_label",
    "notes",
    "tags",
    "indicator_mean",
    "indicator_std",
    "scale_factor",
    "decimals",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open (or create) the database and apply migrations.

    Parameters
    ----------
    db_path:
        Filesystem path or ``":memory:"`` for an in-memory database.

    Returns
    -------
    sqlite3.Connection
        A configured connection with WAL journal mode, foreign keys enabled,
        and ``row_factory`` set to ``sqlite3.Row``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Check schema version and apply pending migrations."""
    version = get_schema_version(conn)

    if version == 0:
        _apply_fresh(conn)

    if get_schema_version(conn) == 1:
        _apply_migration_v2(conn)

    if get_schema_version(conn) == 2:
        _apply_migration_v3(conn)


def _apply_fresh(conn: sqlite3.Connection) -> None:
    """Create all v2 tables, indexes, and record schema version 2."""
    with conn:
        conn.execute(_DDL_SCHEMA_VERSION)
        conn.execute(_DDL_CARDS)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        # Record version — only one row ever lives in this table.
        version_count = conn.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()[0]
        if version_count == 0:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
        else:
            conn.execute(
                "UPDATE schema_version SET version = ?",
                (CURRENT_SCHEMA_VERSION,),
            )


def _apply_migration_v2(conn: sqlite3.Connection) -> None:
    """Upgrade a v1 database to v2: remove state/consecutive_successes, floor stability."""
    # Temporarily disable FK enforcement so we can DROP/RENAME the cards table
    # while review_log still references it.
    conn.execute("PRAGMA foreign_keys=OFF;")
    try:
        with conn:
            # Create the new cards table with v2 schema
            conn.execute("""
                CREATE TABLE cards_v2 (
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
                    stability               REAL    NOT NULL DEFAULT 0.5,
                    last_review             TEXT,
                    due                     TEXT,
                    reps                    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (indicator_id, entity, era)
                )
            """)

            # Copy data, flooring low stability values to 0.5
            conn.execute("""
                INSERT INTO cards_v2
                    (card_id, deck, indicator_id, entity, era, question, answer,
                     unit_prefix, unit_label, notes, tags, indicator_mean,
                     indicator_std, scale_factor, decimals, difficulty,
                     stability, last_review, due, reps)
                SELECT
                    card_id, deck, indicator_id, entity, era, question, answer,
                    unit_prefix, unit_label, notes, tags, indicator_mean,
                    indicator_std, scale_factor, decimals, difficulty,
                    MAX(stability, 0.5), last_review, due, reps
                FROM cards
            """)

            conn.execute("DROP TABLE cards")
            conn.execute("ALTER TABLE cards_v2 RENAME TO cards")

            # Recreate indexes for v2
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_due  ON cards (due, reps)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards (deck)"
            )

            conn.execute("UPDATE schema_version SET version = 2")
    finally:
        conn.execute("PRAGMA foreign_keys=ON;")


def _apply_migration_v3(conn: sqlite3.Connection) -> None:
    """Upgrade v2 -> v3: update defaults for continuous FSRS, clear review_log."""
    conn.execute("PRAGMA foreign_keys=OFF;")
    try:
        with conn:
            conn.execute("""
                CREATE TABLE cards_v3 (
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
                    difficulty              REAL    NOT NULL DEFAULT 7.0,
                    stability               REAL    NOT NULL DEFAULT 0.0067,
                    last_review             TEXT,
                    due                     TEXT,
                    reps                    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (indicator_id, entity, era)
                )
            """)

            conn.execute("""
                INSERT INTO cards_v3
                    (card_id, deck, indicator_id, entity, era, question, answer,
                     unit_prefix, unit_label, notes, tags, indicator_mean,
                     indicator_std, scale_factor, decimals, difficulty,
                     stability, last_review, due, reps)
                SELECT
                    card_id, deck, indicator_id, entity, era, question, answer,
                    unit_prefix, unit_label, notes, tags, indicator_mean,
                    indicator_std, scale_factor, decimals, difficulty,
                    stability, last_review, due, reps
                FROM cards
            """)

            conn.execute("DROP TABLE cards")
            conn.execute("ALTER TABLE cards_v3 RENAME TO cards")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_due  ON cards (due, reps)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards (deck)"
            )

            # Clear review history for clean slate
            conn.execute("DELETE FROM review_log")

            conn.execute("UPDATE schema_version SET version = 3")
    finally:
        conn.execute("PRAGMA foreign_keys=ON;")


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if the table does not exist."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def insert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new card row and return the generated ``card_id``.

    Raises
    ------
    sqlite3.IntegrityError
        If a card with the same ``(indicator_id, entity, era)`` already exists.
    """
    columns = list(card.keys())
    placeholders = ", ".join("?" * len(columns))
    col_clause = ", ".join(columns)
    values = [card[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO cards ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_card(conn: sqlite3.Connection, card_id: int) -> dict | None:
    """Return the card with ``card_id`` as a plain dict, or ``None``."""
    row = conn.execute(
        "SELECT * FROM cards WHERE card_id = ?", (card_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert or update a card identified by ``(indicator_id, entity, era)``.

    On conflict, content fields are updated but scheduling state
    (difficulty, stability, last_review, due, reps) is preserved.

    Returns
    -------
    int
        The ``card_id`` of the inserted or updated row.
    """
    # Build the INSERT clause (all columns provided)
    columns = list(card.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [card[c] for c in columns]

    # Build the DO UPDATE SET clause — update only content fields present in card
    update_parts = []
    for field in _CONTENT_FIELDS:
        if field in card:
            update_parts.append(f"{field} = excluded.{field}")

    if not update_parts:
        # Nothing to update — still need to return the existing card_id
        upsert_sql = (
            f"INSERT INTO cards ({col_clause}) VALUES ({placeholders}) "
            "ON CONFLICT (indicator_id, entity, era) DO NOTHING "
            "RETURNING card_id"
        )
        row = conn.execute(upsert_sql, values).fetchone()
        if row:
            conn.commit()
            return row[0]
        # Row already existed and DO NOTHING fired — fetch the id
        existing = conn.execute(
            "SELECT card_id FROM cards WHERE indicator_id=? AND entity=? AND era=?",
            (card["indicator_id"], card["entity"], card["era"]),
        ).fetchone()
        conn.commit()
        return existing[0]

    update_clause = ", ".join(update_parts)
    upsert_sql = (
        f"INSERT INTO cards ({col_clause}) VALUES ({placeholders}) "
        f"ON CONFLICT (indicator_id, entity, era) DO UPDATE SET {update_clause} "
        "RETURNING card_id"
    )
    row = conn.execute(upsert_sql, values).fetchone()
    conn.commit()
    return row[0]


def update_card_scheduling(
    conn: sqlite3.Connection, card_id: int, fields: dict
) -> None:
    """Update only the scheduling columns for the given card.

    Parameters
    ----------
    fields:
        Mapping of column name → new value. Only recognised scheduling columns
        are accepted; unknown keys and removed columns (state,
        consecutive_successes) are silently ignored.
    """
    allowed = {k: v for k, v in fields.items() if k in _SCHEDULING_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(f"UPDATE cards SET {set_clause} WHERE card_id = ?", values)
    conn.commit()


def get_due_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return cards that are due for review, ordered by priority.

    Priority ordering:
        1. Overdue cards: ``reps > 0`` and ``due <= as_of``, sorted by due ASC
           (oldest overdue first)
        2. New cards: ``reps = 0``, returned in random order

    Cards with ``reps > 0`` whose ``due`` is in the future are excluded.

    Parameters
    ----------
    as_of:
        ISO-8601 timestamp string used as the cutoff for "now".
    deck:
        Optional deck name filter.
    limit:
        Maximum number of cards to return.
    """
    params: list = [as_of]
    deck_clause = ""
    if deck is not None:
        deck_clause = "AND deck = ?"
        params.append(deck)

    limit_clause = ""
    if limit is not None:
        limit_clause = f"LIMIT {int(limit)}"

    sql = f"""
        SELECT *
        FROM cards
        WHERE (reps = 0 OR (reps > 0 AND due <= ?))
          {deck_clause}
        ORDER BY
            CASE WHEN reps > 0 THEN 0 ELSE 1 END,
            CASE WHEN reps > 0 THEN due END ASC,
            CASE WHEN reps = 0 THEN RANDOM() END
        {limit_clause}
    """

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def insert_review(conn: sqlite3.Connection, review: dict) -> int:
    """Insert a review log entry and return the generated ``review_id``."""
    columns = list(review.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [review[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO review_log ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_reviews_for_card(
    conn: sqlite3.Connection, card_id: int
) -> list[dict]:
    """Return all review log entries for ``card_id``, ordered by timestamp."""
    rows = conn.execute(
        "SELECT * FROM review_log WHERE card_id = ? ORDER BY timestamp ASC",
        (card_id,),
    ).fetchall()
    return [dict(row) for row in rows]
