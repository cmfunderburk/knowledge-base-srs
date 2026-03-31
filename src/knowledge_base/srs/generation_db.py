"""SQLite persistence layer for generation cards.

Provides schema creation and CRUD operations for the generation_cards and
generation_review_log tables used by the generation-phase SRS system.

This module is COMPLETELY SEPARATE from db.py. It does not import from or
modify db.py. Both modules can coexist in the same SQLite file because all
table names are prefixed with 'generation_'.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 1

_DDL_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS generation_schema_version (
    version INTEGER NOT NULL
);
"""

_DDL_GENERATION_CARDS = """
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
);
"""

_DDL_GENERATION_REVIEW_LOG = """
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
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_gen_cards_due      ON generation_cards (due, reps);
CREATE INDEX IF NOT EXISTS idx_gen_cards_deck     ON generation_cards (deck);
CREATE INDEX IF NOT EXISTS idx_gen_cards_phase    ON generation_cards (phase);
CREATE INDEX IF NOT EXISTS idx_gen_review_log_card ON generation_review_log (card_id);
"""

# ---------------------------------------------------------------------------
# Field sets for targeted update functions
# ---------------------------------------------------------------------------

_SCHEDULING_FIELDS = frozenset({
    "difficulty",
    "stability",
    "last_review",
    "due",
    "reps",
})

_PHASE_FIELDS = frozenset({
    "masking_level",
    "phase",
    "consecutive_max_passes",
})

# Content fields updated on upsert (scheduling and phase state are preserved)
_CONTENT_FIELDS = (
    "deck",
    "topic_id",
    "question",
    "answer",
    "tags",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_generation_db(
    db_path: str | Path = ":memory:",
    conn: sqlite3.Connection | None = None,
) -> sqlite3.Connection:
    """Open (or create) the database and initialise generation tables.

    Parameters
    ----------
    db_path:
        Filesystem path or ``":memory:"`` for an in-memory database. Ignored
        when ``conn`` is provided.
    conn:
        An existing connection to use. Useful when sharing a file with the
        main SRS database. When provided, ``db_path`` is ignored.

    Returns
    -------
    sqlite3.Connection
        A configured connection with WAL journal mode, foreign keys enabled,
        and ``row_factory`` set to ``sqlite3.Row``.
    """
    if conn is None:
        conn = sqlite3.connect(str(db_path))

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    with conn:
        conn.execute(_DDL_SCHEMA_VERSION)
        conn.execute(_DDL_GENERATION_CARDS)
        conn.execute(_DDL_GENERATION_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)

        # Ensure exactly one version row exists
        version_count = conn.execute(
            "SELECT COUNT(*) FROM generation_schema_version"
        ).fetchone()[0]
        if version_count == 0:
            conn.execute(
                "INSERT INTO generation_schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
        else:
            conn.execute(
                "UPDATE generation_schema_version SET version = ?",
                (CURRENT_SCHEMA_VERSION,),
            )

    return conn


def insert_generation_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new generation card row and return the generated ``card_id``.

    Raises
    ------
    sqlite3.IntegrityError
        If a card with the same ``(deck, los_id)`` already exists.
    """
    columns = list(card.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [card[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_generation_card(conn: sqlite3.Connection, card_id: int) -> dict | None:
    """Return the generation card with ``card_id`` as a plain dict, or ``None``."""
    row = conn.execute(
        "SELECT * FROM generation_cards WHERE card_id = ?", (card_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_generation_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert or update a generation card identified by ``(deck, los_id)``.

    On conflict, content fields (deck, topic_id, question, answer, tags) are
    updated but scheduling state (difficulty, stability, last_review, due,
    reps) and phase state (masking_level, phase, consecutive_max_passes) are
    preserved.

    Returns
    -------
    int
        The ``card_id`` of the inserted or updated row.
    """
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
        upsert_sql = (
            f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders}) "
            "ON CONFLICT (deck, los_id) DO NOTHING "
            "RETURNING card_id"
        )
        row = conn.execute(upsert_sql, values).fetchone()
        if row:
            conn.commit()
            return row[0]
        # Row already existed and DO NOTHING fired — fetch the id
        existing = conn.execute(
            "SELECT card_id FROM generation_cards WHERE deck=? AND los_id=?",
            (card["deck"], card["los_id"]),
        ).fetchone()
        conn.commit()
        return existing[0]

    update_clause = ", ".join(update_parts)
    upsert_sql = (
        f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders}) "
        f"ON CONFLICT (deck, los_id) DO UPDATE SET {update_clause} "
        "RETURNING card_id"
    )
    row = conn.execute(upsert_sql, values).fetchone()
    conn.commit()
    return row[0]


def update_generation_scheduling(
    conn: sqlite3.Connection, card_id: int, fields: dict
) -> None:
    """Update only the FSRS scheduling columns for the given generation card.

    Parameters
    ----------
    fields:
        Mapping of column name → new value. Only recognised scheduling
        columns are accepted; unknown keys are silently ignored.
    """
    allowed = {k: v for k, v in fields.items() if k in _SCHEDULING_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(
        f"UPDATE generation_cards SET {set_clause} WHERE card_id = ?", values
    )
    conn.commit()


def update_generation_phase(
    conn: sqlite3.Connection, card_id: int, fields: dict
) -> None:
    """Update only the phase-progression columns for the given generation card.

    Parameters
    ----------
    fields:
        Mapping of column name → new value. Only recognised phase columns
        are accepted; unknown keys are silently ignored.
    """
    allowed = {k: v for k, v in fields.items() if k in _PHASE_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(
        f"UPDATE generation_cards SET {set_clause} WHERE card_id = ?", values
    )
    conn.commit()


def get_generation_phase_cards(
    conn: sqlite3.Connection,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return all cards in the generation phase, in random order.

    Parameters
    ----------
    deck:
        Optional deck name filter.
    limit:
        Maximum number of cards to return.
    """
    deck_clause = ""
    params: list = []

    if deck is not None:
        deck_clause = "AND deck = ?"
        params.append(deck)

    limit_clause = ""
    if limit is not None:
        limit_clause = f"LIMIT {int(limit)}"

    sql = f"""
        SELECT *
        FROM generation_cards
        WHERE phase = 'generation'
          {deck_clause}
        ORDER BY RANDOM()
        {limit_clause}
    """

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_due_generation_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return recall-phase cards whose due date is on or before ``as_of``.

    Only cards with ``phase = 'recall'`` and ``due <= as_of`` are returned,
    ordered by due date ascending (oldest overdue first).

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
        FROM generation_cards
        WHERE phase = 'recall'
          AND due <= ?
          {deck_clause}
        ORDER BY due ASC
        {limit_clause}
    """

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def insert_generation_review(conn: sqlite3.Connection, review: dict) -> int:
    """Insert a generation review log entry and return the generated ``review_id``."""
    columns = list(review.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [review[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO generation_review_log ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid
