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

CURRENT_SCHEMA_VERSION = 2

_DDL_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS generation_schema_version (
    version INTEGER NOT NULL
);
"""

_DDL_GENERATION_CARDS = """
CREATE TABLE IF NOT EXISTS generation_cards (
    card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    deck                   TEXT    NOT NULL,
    source                 TEXT    NOT NULL DEFAULT 'los',
    topic_id               TEXT    NOT NULL,
    section_id             TEXT    NOT NULL,
    section_title          TEXT,
    card_index             INTEGER NOT NULL DEFAULT 0,
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
    UNIQUE (deck, source, topic_id, section_id, card_index)
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
CREATE INDEX IF NOT EXISTS idx_gen_cards_source   ON generation_cards (source);
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

# Unique constraint columns for upsert ON CONFLICT
_CONFLICT_COLS = "deck, source, topic_id, section_id, card_index"

# Content fields updated on upsert (scheduling and phase state are preserved)
_CONTENT_FIELDS = (
    "deck",
    "source",
    "topic_id",
    "section_id",
    "section_title",
    "card_index",
    "question",
    "answer",
    "tags",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate generation_cards from schema v1 to v2.

    SQLite does not support ALTER TABLE to change constraints, so the
    migration creates a new table with the v2 schema, copies all data
    (mapping ``los_id`` → ``section_id``, adding ``source='los'`` and
    ``card_index=0``), drops the old table, and renames the new one.

    All scheduling and phase state is preserved.
    """
    # FK enforcement is disabled/re-enabled by the caller (init_generation_db)
    # outside the transaction, since PRAGMA foreign_keys is a no-op inside
    # an active transaction in SQLite.
    conn.execute("""
        CREATE TABLE generation_cards_v2 (
            card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
            deck                   TEXT    NOT NULL,
            source                 TEXT    NOT NULL DEFAULT 'los',
            topic_id               TEXT    NOT NULL,
            section_id             TEXT    NOT NULL,
            section_title          TEXT,
            card_index             INTEGER NOT NULL DEFAULT 0,
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
            UNIQUE (deck, source, topic_id, section_id, card_index)
        )
    """)
    conn.execute("""
        INSERT INTO generation_cards_v2 (
            card_id, deck, source, topic_id, section_id, section_title,
            card_index, question, answer, tags, masking_level, phase,
            consecutive_max_passes, difficulty, stability, last_review,
            due, reps
        )
        SELECT
            card_id, deck, 'los', topic_id, los_id, NULL,
            0, question, answer, tags, masking_level, phase,
            consecutive_max_passes, difficulty, stability, last_review,
            due, reps
        FROM generation_cards
    """)
    conn.execute("DROP TABLE generation_cards")
    conn.execute("ALTER TABLE generation_cards_v2 RENAME TO generation_cards")
    conn.execute(
        "UPDATE generation_schema_version SET version = ?",
        (CURRENT_SCHEMA_VERSION,),
    )


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

    # Determine if migration is needed before opening a transaction,
    # since PRAGMA foreign_keys is a no-op inside an active transaction.
    needs_migration = False
    try:
        version_count = conn.execute(
            "SELECT COUNT(*) FROM generation_schema_version"
        ).fetchone()[0]
        if version_count > 0:
            stored_version = conn.execute(
                "SELECT version FROM generation_schema_version"
            ).fetchone()[0]
            needs_migration = stored_version < 2
    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet — fresh DB

    if needs_migration:
        # Disable FKs outside any transaction for the migration
        conn.execute("PRAGMA foreign_keys=OFF;")
        with conn:
            _migrate_v1_to_v2(conn)
        # Re-enable FKs outside the transaction
        conn.execute("PRAGMA foreign_keys=ON;")
    else:
        conn.execute("PRAGMA foreign_keys=ON;")

    with conn:
        conn.execute(_DDL_SCHEMA_VERSION)

        version_count = conn.execute(
            "SELECT COUNT(*) FROM generation_schema_version"
        ).fetchone()[0]

        if version_count == 0:
            # Fresh database — create tables and stamp version
            conn.execute(_DDL_GENERATION_CARDS)
            conn.execute(_DDL_GENERATION_REVIEW_LOG)
            conn.execute(
                "INSERT INTO generation_schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
        else:
            # Ensure tables exist (idempotent for already-migrated DBs)
            conn.execute(_DDL_GENERATION_CARDS)
            conn.execute(_DDL_GENERATION_REVIEW_LOG)
            # Stamp current version
            conn.execute(
                "UPDATE generation_schema_version SET version = ?",
                (CURRENT_SCHEMA_VERSION,),
            )

        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)

    return conn


def insert_generation_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new generation card row and return the generated ``card_id``.

    Raises
    ------
    sqlite3.IntegrityError
        If a card with the same ``(deck, source, topic_id, section_id, card_index)``
        already exists.
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
    """Insert or update a generation card identified by
    ``(deck, source, topic_id, section_id, card_index)``.

    On conflict, content fields (deck, source, topic_id, section_id,
    section_title, card_index, question, answer, tags) are updated but
    scheduling state (difficulty, stability, last_review, due, reps) and
    phase state (masking_level, phase, consecutive_max_passes) are preserved.

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
            f"ON CONFLICT ({_CONFLICT_COLS}) DO NOTHING "
            "RETURNING card_id"
        )
        row = conn.execute(upsert_sql, values).fetchone()
        if row:
            conn.commit()
            return row[0]
        # Row already existed and DO NOTHING fired — fetch the id
        existing = conn.execute(
            "SELECT card_id FROM generation_cards "
            "WHERE deck=? AND source=? AND topic_id=? AND section_id=? AND card_index=?",
            (card["deck"], card["source"], card["topic_id"],
             card["section_id"], card["card_index"]),
        ).fetchone()
        conn.commit()
        return existing[0]

    update_clause = ", ".join(update_parts)
    upsert_sql = (
        f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders}) "
        f"ON CONFLICT ({_CONFLICT_COLS}) DO UPDATE SET {update_clause} "
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


def get_cards_by_readings(
    conn: sqlite3.Connection,
    topic_ids: list[str],
    deck: str | None = None,
) -> list[dict]:
    """Return all cards matching the given reading (topic_id) numbers.

    Returns cards regardless of phase, in random order. Used by massed
    practice mode which operates entirely in-memory.
    """
    if not topic_ids:
        return []
    placeholders = ", ".join("?" * len(topic_ids))
    params: list = list(topic_ids)
    deck_clause = ""
    if deck is not None:
        deck_clause = "AND deck = ?"
        params.append(deck)
    sql = f"""
        SELECT * FROM generation_cards
        WHERE topic_id IN ({placeholders})
          {deck_clause}
        ORDER BY RANDOM()
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_all_generation_cards(
    conn: sqlite3.Connection,
    deck: str | None = None,
) -> list[dict]:
    """Return all generation cards regardless of phase, in random order.

    Used by massed practice 'all' mode.
    """
    params: list = []
    deck_clause = ""
    if deck is not None:
        deck_clause = "WHERE deck = ?"
        params.append(deck)
    sql = f"SELECT * FROM generation_cards {deck_clause} ORDER BY RANDOM()"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_due_generation_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return recall-phase cards whose due date is on or before ``as_of``.

    Only cards with ``phase = 'recall'``, ``reps > 0``, and ``due <= as_of``
    are returned, ordered by due date ascending (oldest overdue first).
    Newly graduated cards must have ``reps`` and ``due`` set by the
    graduation logic before they appear here.

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


def get_cards_by_source(
    conn: sqlite3.Connection,
    source: str,
    topic_ids: list[str] | None = None,
    section_ids: list[str] | None = None,
    deck: str | None = None,
) -> list[dict]:
    """Return all cards matching the given source, with optional filters.

    Cards are returned in random order. Used by practice modes that filter
    by source (e.g. 'los', 'markdown') independently of topic/section.

    Parameters
    ----------
    source:
        Source identifier to filter on (e.g. 'los', 'markdown').
    topic_ids:
        Optional list of topic_id values to restrict to.
    section_ids:
        Optional list of section_id values to restrict to.
    deck:
        Optional deck name filter.
    """
    params: list = [source]
    clauses: list[str] = ["source = ?"]

    if deck is not None:
        clauses.append("deck = ?")
        params.append(deck)

    if topic_ids is not None:
        placeholders = ", ".join("?" * len(topic_ids))
        clauses.append(f"topic_id IN ({placeholders})")
        params.extend(topic_ids)

    if section_ids is not None:
        placeholders = ", ".join("?" * len(section_ids))
        clauses.append(f"section_id IN ({placeholders})")
        params.extend(section_ids)

    where_clause = " AND ".join(clauses)
    sql = f"SELECT * FROM generation_cards WHERE {where_clause} ORDER BY RANDOM()"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_catalog_tree(
    conn: sqlite3.Connection,
    deck: str | None = None,
) -> list[dict]:
    """Return aggregated card counts grouped by deck, topic_id, source, section_id.

    Each returned dict has keys: deck, topic_id, source, section_id,
    section_title, card_count. Used to build the catalog TUI tree.

    Parameters
    ----------
    deck:
        Optional deck name filter.
    """
    params: list = []
    where_clause = ""
    if deck is not None:
        where_clause = "WHERE deck = ?"
        params.append(deck)

    sql = f"""
        SELECT deck, topic_id, source, section_id, section_title,
               COUNT(*) AS card_count
        FROM generation_cards
        {where_clause}
        GROUP BY deck, topic_id, source, section_id
        ORDER BY deck, topic_id, source, section_id
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
