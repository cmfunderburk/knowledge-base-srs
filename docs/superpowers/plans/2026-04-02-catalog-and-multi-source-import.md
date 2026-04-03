# Catalog TUI & Multi-Source Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browsable catalog TUI, markdown import pipeline, and paste-and-drill mode so users can discover, import, and practice generation cards across multiple sources and sections.

**Architecture:** Extend the generation card schema with `source`, `section_id` (renamed from `los_id`), `section_title`, and `card_index` columns. Build a markdown parser for two heading conventions (section-keyed and LOS-keyed). Add a Textual Tree-based catalog screen as the default entry point for `review-gen`. Preserve all existing CLI flags and behavior.

**Tech Stack:** Python 3.12+, sqlite3, Textual (TUI), pytest, re (markdown parsing)

**Spec:** `docs/superpowers/specs/2026-04-02-catalog-and-multi-source-import-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/knowledge_base/srs/generation_db.py` | Modify: schema migration (v1→v2), rename `los_id`→`section_id`, add `source`/`section_title`/`card_index` columns, new unique constraint, new query functions |
| `src/knowledge_base/srs/generation_import.py` | Modify: update LOS import to use new column names (`section_id` instead of `los_id`, add `source`/`card_index`) |
| `src/knowledge_base/srs/md_importer.py` | Create: markdown parser and `gen-import-md` CLI entry point |
| `src/knowledge_base/srs/catalog.py` | Create: Textual catalog screen widget with tree browser and selection logic |
| `src/knowledge_base/srs/generation_tui.py` | Modify: integrate catalog screen, add `--paste`/`--source`/`--section`/`--save-as`/`--split-by` flags, update header display, update `los_id` references to `section_id` |
| `pyproject.toml` | Modify: add `gen-import-md` script entry point |
| `tests/test_generation_db.py` | Modify: update all `los_id` references, add migration and new query tests |
| `tests/test_generation_import.py` | Modify: update `los_id` references to `section_id` |
| `tests/test_md_importer.py` | Create: tests for markdown parser |
| `tests/test_catalog.py` | Create: tests for catalog tree builder and selection logic |

---

### Task 1: Schema Migration — Add New Columns and Rename `los_id`

**Files:**
- Modify: `src/knowledge_base/srs/generation_db.py:19-95` (schema constants, field sets)
- Modify: `src/knowledge_base/srs/generation_db.py:102-154` (init function)
- Test: `tests/test_generation_db.py`

- [ ] **Step 1: Write failing tests for the migration**

Add a new test class in `tests/test_generation_db.py`:

```python
class TestSchemaV2Migration:
    """Tests for v1 → v2 migration: los_id renamed to section_id, new columns added."""

    def _create_v1_db(self):
        """Create a v1 database with the old schema and some cards."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("""
            CREATE TABLE generation_schema_version (
                version INTEGER NOT NULL
            )
        """)
        conn.execute("INSERT INTO generation_schema_version (version) VALUES (1)")
        conn.execute("""
            CREATE TABLE generation_cards (
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
            CREATE TABLE generation_review_log (
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
        # Insert a card with scheduling state to verify preservation
        conn.execute("""
            INSERT INTO generation_cards
                (deck, topic_id, los_id, question, answer, tags, masking_level, phase, difficulty, stability, reps)
            VALUES
                ('cfa_level1', '1', '1.a', 'What is LOS 1.a?', 'interpret interest rates', '[]', 2, 'recall', 7.5, 3.2, 5)
        """)
        conn.commit()
        return conn

    def test_migration_renames_los_id_to_section_id(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(generation_cards)").fetchall()]
        assert "section_id" in cols
        assert "los_id" not in cols

    def test_migration_adds_source_column(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(generation_cards)").fetchall()]
        assert "source" in cols

    def test_migration_adds_section_title_column(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(generation_cards)").fetchall()]
        assert "section_title" in cols

    def test_migration_adds_card_index_column(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(generation_cards)").fetchall()]
        assert "card_index" in cols

    def test_migration_preserves_existing_card_data(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        card = dict(conn.execute("SELECT * FROM generation_cards WHERE card_id = 1").fetchone())
        assert card["section_id"] == "1.a"
        assert card["source"] == "los"
        assert card["card_index"] == 0
        # Scheduling state preserved
        assert card["difficulty"] == 7.5
        assert card["stability"] == 3.2
        assert card["reps"] == 5
        assert card["phase"] == "recall"
        assert card["masking_level"] == 2

    def test_migration_updates_schema_version(self):
        conn = self._create_v1_db()
        conn = init_generation_db(conn=conn)
        version = conn.execute("SELECT version FROM generation_schema_version").fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION

    def test_fresh_db_creates_v2_schema_directly(self):
        conn = init_generation_db()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(generation_cards)").fetchall()]
        assert "section_id" in cols
        assert "source" in cols
        assert "section_title" in cols
        assert "card_index" in cols
        assert "los_id" not in cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generation_db.py::TestSchemaV2Migration -v`
Expected: FAIL — `section_id` not in columns, migration not implemented

- [ ] **Step 3: Update the schema DDL and field sets**

In `generation_db.py`, update the schema constants:

Change `CURRENT_SCHEMA_VERSION` from `1` to `2` (line 19).

Replace `_DDL_GENERATION_CARDS` (lines 27-46) with:

```python
_DDL_GENERATION_CARDS = """
CREATE TABLE IF NOT EXISTS generation_cards (
    card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    deck                   TEXT    NOT NULL,
    topic_id               TEXT    NOT NULL,
    source                 TEXT    NOT NULL DEFAULT 'los',
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
```

Add `"source"` and `"section_title"` to `_CONTENT_FIELDS` (lines 88-94):

```python
_CONTENT_FIELDS = (
    "deck",
    "topic_id",
    "source",
    "section_id",
    "section_title",
    "card_index",
    "question",
    "answer",
    "tags",
)
```

Add an index on `source` to `_DDL_INDEXES`:

```python
_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_gen_cards_due      ON generation_cards (due, reps);
CREATE INDEX IF NOT EXISTS idx_gen_cards_deck     ON generation_cards (deck);
CREATE INDEX IF NOT EXISTS idx_gen_cards_phase    ON generation_cards (phase);
CREATE INDEX IF NOT EXISTS idx_gen_cards_source   ON generation_cards (source);
CREATE INDEX IF NOT EXISTS idx_gen_review_log_card ON generation_review_log (card_id);
"""
```

- [ ] **Step 4: Implement the v1→v2 migration in `init_generation_db`**

Add a migration function and call it from `init_generation_db`. Insert the migration function before `init_generation_db`:

```python
def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate schema from v1 to v2.

    - Rename los_id → section_id
    - Add source, section_title, card_index columns
    - Rebuild unique constraint to (deck, source, topic_id, section_id, card_index)
    """
    # SQLite doesn't support ALTER TABLE RENAME COLUMN before 3.25.0,
    # but Python 3.12 ships with SQLite 3.40+, so we can use it directly.
    conn.execute("ALTER TABLE generation_cards RENAME COLUMN los_id TO section_id")
    conn.execute("ALTER TABLE generation_cards ADD COLUMN source TEXT NOT NULL DEFAULT 'los'")
    conn.execute("ALTER TABLE generation_cards ADD COLUMN section_title TEXT")
    conn.execute("ALTER TABLE generation_cards ADD COLUMN card_index INTEGER NOT NULL DEFAULT 0")

    # Rebuild unique constraint: drop old, create new.
    # SQLite doesn't support DROP CONSTRAINT, so we create a new unique index
    # and drop the old auto-generated one.
    # The old UNIQUE(deck, los_id) created an auto-index named
    # sqlite_autoindex_generation_cards_1. We need to recreate the table
    # to change the constraint. Instead, we add a unique index explicitly.
    # The old autoindex will conflict, so we rebuild the table.

    # Rebuild approach: create new table, copy data, drop old, rename new.
    conn.execute("""
        CREATE TABLE generation_cards_v2 (
            card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
            deck                   TEXT    NOT NULL,
            topic_id               TEXT    NOT NULL,
            source                 TEXT    NOT NULL DEFAULT 'los',
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
            card_id, deck, topic_id, source, section_id, section_title, card_index,
            question, answer, tags, masking_level, phase, consecutive_max_passes,
            difficulty, stability, last_review, due, reps
        )
        SELECT
            card_id, deck, topic_id, 'los', section_id, NULL, 0,
            question, answer, tags, masking_level, phase, consecutive_max_passes,
            difficulty, stability, last_review, due, reps
        FROM generation_cards
    """)
    conn.execute("DROP TABLE generation_cards")
    conn.execute("ALTER TABLE generation_cards_v2 RENAME TO generation_cards")

    conn.execute(
        "UPDATE generation_schema_version SET version = 2"
    )
```

Update `init_generation_db` to check the stored version and run the migration. Replace the version-management block (lines 139-152) with:

```python
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
            stored_version = conn.execute(
                "SELECT version FROM generation_schema_version"
            ).fetchone()[0]
            if stored_version < 2:
                _migrate_v1_to_v2(conn)
            elif stored_version < CURRENT_SCHEMA_VERSION:
                conn.execute(
                    "UPDATE generation_schema_version SET version = ?",
                    (CURRENT_SCHEMA_VERSION,),
                )
```

- [ ] **Step 5: Update all `los_id` references in CRUD functions**

In `generation_db.py`, update the following:

`insert_generation_card` docstring (line 163): change `(deck, los_id)` → `(deck, source, topic_id, section_id, card_index)`

`upsert_generation_card` (lines 185-235):
- Docstring: change `(deck, los_id)` → `(deck, source, topic_id, section_id, card_index)`
- Line 212: change `ON CONFLICT (deck, los_id)` → `ON CONFLICT (deck, source, topic_id, section_id, card_index)`
- Lines 220-222: change the fallback lookup:
  ```python
  existing = conn.execute(
      "SELECT card_id FROM generation_cards WHERE deck=? AND source=? AND topic_id=? AND section_id=? AND card_index=?",
      (card["deck"], card["source"], card["topic_id"], card["section_id"], card["card_index"]),
  ).fetchone()
  ```
- Line 230: change `ON CONFLICT (deck, los_id)` → `ON CONFLICT (deck, source, topic_id, section_id, card_index)`

- [ ] **Step 6: Run tests to verify migration tests pass**

Run: `uv run pytest tests/test_generation_db.py::TestSchemaV2Migration -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Update existing test helpers and tests for `los_id` → `section_id`**

In `tests/test_generation_db.py`, update the `_minimal_card` helper (line 24-35):

```python
def _minimal_card(**overrides) -> dict:
    """Return a minimal valid generation card dict with sensible defaults."""
    base = {
        "deck": "cfa_level1",
        "topic_id": "1",
        "source": "los",
        "section_id": "1.a",
        "card_index": 0,
        "question": "What is the time value of money?",
        "answer": "Money available now is worth more than the same amount in the future.",
        "tags": "[]",
    }
    base.update(overrides)
    return base
```

Search for all `los_id` references in the test file and replace with `section_id`. Key places:
- Any test that creates cards with `los_id=` kwarg → use `section_id=`
- Any assertion on `card["los_id"]` → `card["section_id"]`

- [ ] **Step 8: Run the full generation_db test suite**

Run: `uv run pytest tests/test_generation_db.py -v`
Expected: All tests PASS

- [ ] **Step 9: Update `generation_import.py` to use new column names**

In `generation_import.py`, update the upsert call (lines 86-93):

```python
            upsert_generation_card(conn, {
                "deck": deck,
                "topic_id": str(number),
                "source": "los",
                "section_id": los_id,
                "card_index": 0,
                "question": question,
                "answer": answer,
                "tags": tags,
            })
```

- [ ] **Step 10: Update generation import tests for `section_id`**

In `tests/test_generation_import.py`, update any assertions that reference `los_id` to use `section_id` instead. The key assertions will be checking `card["section_id"]` instead of `card["los_id"]`.

- [ ] **Step 11: Update `generation_tui.py` — replace all `los_id` with `section_id`**

In `generation_tui.py`, do a find-and-replace of `los_id` → `section_id` and `["los_id"]` → `["section_id"]`. Key locations:
- `_los_sort_key` function (lines 52-56): rename to `_section_sort_key`, change `card["los_id"]` → `card["section_id"]`
- Header display (lines 372-408): change `los_id` references to `section_id`
- Any other references throughout the file

- [ ] **Step 12: Run the full test suite**

Run: `uv run pytest -v`
Expected: All 377+ tests PASS

- [ ] **Step 13: Commit**

```bash
git add src/knowledge_base/srs/generation_db.py src/knowledge_base/srs/generation_import.py src/knowledge_base/srs/generation_tui.py tests/test_generation_db.py tests/test_generation_import.py
git commit -m "feat: migrate generation card schema to v2 with source, section_id, card_index

Rename los_id → section_id, add source/section_title/card_index columns.
Unique constraint now (deck, source, topic_id, section_id, card_index).
Existing cards backfilled with source='los', card_index=0.
All references updated across db, import, TUI, and tests."
```

---

### Task 2: New Query Functions for Source/Section Filtering

**Files:**
- Modify: `src/knowledge_base/srs/generation_db.py`
- Test: `tests/test_generation_db.py`

- [ ] **Step 1: Write failing tests for new query functions**

Add to `tests/test_generation_db.py`:

```python
class TestSourceSectionQueries:
    """Tests for source- and section-level card queries."""

    def _populate(self, conn):
        """Insert cards across multiple sources and sections."""
        cards = [
            {"deck": "cfa_level1", "topic_id": "1", "source": "los", "section_id": "1.a", "card_index": 0,
             "question": "LOS 1.a", "answer": "interpret interest rates", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "los", "section_id": "1.b", "card_index": 0,
             "question": "LOS 1.b", "answer": "calculate returns", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "official", "section_id": "1.2", "card_index": 0,
             "question": "Official 1.2 bullet 1", "answer": "interest rate interpretation", "tags": "[]",
             "section_title": "Interest Rates and TVM"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "official", "section_id": "1.2", "card_index": 1,
             "question": "Official 1.2 bullet 2", "answer": "risk premiums", "tags": "[]",
             "section_title": "Interest Rates and TVM"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "official", "section_id": "1.3", "card_index": 0,
             "question": "Official 1.3 bullet 1", "answer": "holding period return", "tags": "[]",
             "section_title": "Rates of Return"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "schweser", "section_id": "1.a", "card_index": 0,
             "question": "Schweser 1.a bullet 1", "answer": "interest rate as required return", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "schweser", "section_id": "1.a", "card_index": 1,
             "question": "Schweser 1.a bullet 2", "answer": "nominal risk-free rate", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "2", "source": "los", "section_id": "2.a", "card_index": 0,
             "question": "LOS 2.a", "answer": "TVM concepts", "tags": "[]"},
        ]
        for card in cards:
            insert_generation_card(conn, card)
        return cards

    def test_get_cards_by_source(self):
        conn = init_generation_db()
        self._populate(conn)
        cards = get_cards_by_source(conn, source="official", deck="cfa_level1")
        assert len(cards) == 3
        assert all(c["source"] == "official" for c in cards)

    def test_get_cards_by_source_and_topic(self):
        conn = init_generation_db()
        self._populate(conn)
        cards = get_cards_by_source(conn, source="official", topic_ids=["1"], deck="cfa_level1")
        assert len(cards) == 3

    def test_get_cards_by_source_and_section(self):
        conn = init_generation_db()
        self._populate(conn)
        cards = get_cards_by_source(conn, source="official", section_ids=["1.2"], deck="cfa_level1")
        assert len(cards) == 2
        assert all(c["section_id"] == "1.2" for c in cards)

    def test_get_cards_by_source_and_topic_and_section(self):
        conn = init_generation_db()
        self._populate(conn)
        cards = get_cards_by_source(conn, source="schweser", topic_ids=["1"], section_ids=["1.a"], deck="cfa_level1")
        assert len(cards) == 2

    def test_get_cards_by_readings_includes_all_sources(self):
        """Existing get_cards_by_readings should return cards from all sources."""
        conn = init_generation_db()
        self._populate(conn)
        cards = get_cards_by_readings(conn, topic_ids=["1"], deck="cfa_level1")
        assert len(cards) == 7  # 2 los + 3 official + 2 schweser

    def test_get_catalog_tree(self):
        conn = init_generation_db()
        self._populate(conn)
        tree = get_catalog_tree(conn, deck="cfa_level1")
        # tree is list of dicts: {topic_id, source, section_id, section_title, card_count}
        assert len(tree) > 0
        official_1_2 = [r for r in tree if r["source"] == "official" and r["section_id"] == "1.2"]
        assert len(official_1_2) == 1
        assert official_1_2[0]["card_count"] == 2
        assert official_1_2[0]["section_title"] == "Interest Rates and TVM"

    def test_get_catalog_tree_no_deck_filter(self):
        conn = init_generation_db()
        self._populate(conn)
        tree = get_catalog_tree(conn)
        assert len(tree) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generation_db.py::TestSourceSectionQueries -v`
Expected: FAIL — `get_cards_by_source` and `get_catalog_tree` not defined

- [ ] **Step 3: Implement `get_cards_by_source`**

Add to `generation_db.py`:

```python
def get_cards_by_source(
    conn: sqlite3.Connection,
    source: str,
    topic_ids: list[str] | None = None,
    section_ids: list[str] | None = None,
    deck: str | None = None,
) -> list[dict]:
    """Return cards matching the given source, with optional topic/section filters.

    Cards are returned in random order. Used by practice modes.
    """
    clauses = ["source = ?"]
    params: list = [source]

    if deck is not None:
        clauses.append("deck = ?")
        params.append(deck)

    if topic_ids:
        placeholders = ", ".join("?" * len(topic_ids))
        clauses.append(f"topic_id IN ({placeholders})")
        params.extend(topic_ids)

    if section_ids:
        placeholders = ", ".join("?" * len(section_ids))
        clauses.append(f"section_id IN ({placeholders})")
        params.extend(section_ids)

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM generation_cards WHERE {where} ORDER BY RANDOM()"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Implement `get_catalog_tree`**

Add to `generation_db.py`:

```python
def get_catalog_tree(
    conn: sqlite3.Connection,
    deck: str | None = None,
) -> list[dict]:
    """Return aggregated card counts grouped by topic, source, and section.

    Returns a list of dicts with keys: deck, topic_id, source, section_id,
    section_title, card_count. Used to build the catalog TUI tree.
    """
    params: list = []
    deck_clause = ""
    if deck is not None:
        deck_clause = "WHERE deck = ?"
        params.append(deck)

    sql = f"""
        SELECT deck, topic_id, source, section_id,
               section_title, COUNT(*) AS card_count
        FROM generation_cards
        {deck_clause}
        GROUP BY deck, topic_id, source, section_id
        ORDER BY deck, topic_id, source, section_id
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_generation_db.py::TestSourceSectionQueries -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/knowledge_base/srs/generation_db.py tests/test_generation_db.py
git commit -m "feat: add get_cards_by_source and get_catalog_tree query functions

Source/section/topic filtering for practice modes.
Catalog tree query aggregates card counts by hierarchy level."
```

---

### Task 3: Markdown Import Parser

**Files:**
- Create: `src/knowledge_base/srs/md_importer.py`
- Create: `tests/test_md_importer.py`

- [ ] **Step 1: Write failing tests for section-keyed parsing**

Create `tests/test_md_importer.py`:

```python
"""Tests for srs/md_importer.py — markdown import pipeline."""

import pytest

from knowledge_base.srs.md_importer import parse_markdown


class TestSectionKeyedParsing:
    """Tests for section-keyed markdown (e.g., '- 1.2: Title' format)."""

    def test_parses_dash_section_headings(self):
        md = """\
- 1.2: Interest Rates and Time Value of Money
\t- An interest rate can have three interpretations.
\t- The nominal risk-free rate is the sum of the real risk-free rate and inflation.
- 1.3: Rates of Return
\t- Holding period return measures return over a specific period.
"""
        sections = parse_markdown(md)
        assert len(sections) == 2
        assert sections[0]["section_id"] == "1.2"
        assert sections[0]["section_title"] == "Interest Rates and Time Value of Money"
        assert len(sections[0]["cards"]) == 2
        assert sections[0]["cards"][0] == "An interest rate can have three interpretations."
        assert sections[1]["section_id"] == "1.3"
        assert len(sections[1]["cards"]) == 1

    def test_parses_hash_section_headings(self):
        md = """\
## 1.2: Interest Rates
- First bullet.
- Second bullet.
"""
        sections = parse_markdown(md)
        assert len(sections) == 1
        assert sections[0]["section_id"] == "1.2"
        assert sections[0]["section_title"] == "Interest Rates"
        assert len(sections[0]["cards"]) == 2

    def test_skips_content_before_first_section(self):
        md = """\
**Learning Outcomes**
- [ ] interpret interest rates

---

**Learning Module Overview**
- 1.2: Interest Rates
\t- A bullet under 1.2.
"""
        sections = parse_markdown(md)
        assert len(sections) == 1
        assert sections[0]["section_id"] == "1.2"

    def test_sub_bullets_folded_into_parent(self):
        md = """\
- 1.2: Interest Rates
\t- An interest rate can be: (1) a required rate of return, (2) a discount rate.
\t\t- The required rate of return is the minimum rate an investor will accept.
\t\t- The discount rate is used to calculate present value.
\t- The nominal risk-free rate includes inflation.
"""
        sections = parse_markdown(md)
        assert len(sections[0]["cards"]) == 2
        # Sub-bullets folded into parent
        assert "required rate of return is the minimum" in sections[0]["cards"][0]

    def test_empty_section_skipped(self):
        md = """\
- 1.2: Interest Rates
- 1.3: Rates of Return
\t- A bullet.
"""
        sections = parse_markdown(md)
        assert len(sections) == 1
        assert sections[0]["section_id"] == "1.3"


class TestLosKeyedParsing:
    """Tests for LOS-keyed markdown (e.g., '### LOS 1.a' format)."""

    def test_parses_los_headings(self):
        md = """\
### LOS 1.a
- An interest rate can be interpreted as the rate of return required in equilibrium.
- Securities may have several risks increasing required return.
### LOS 1.b
- Holding period return measures return over a specific period.
"""
        sections = parse_markdown(md)
        assert len(sections) == 2
        assert sections[0]["section_id"] == "1.a"
        assert sections[0]["section_title"] is None
        assert len(sections[0]["cards"]) == 2
        assert sections[1]["section_id"] == "1.b"

    def test_consecutive_lines_joined_as_single_card(self):
        md = """\
### LOS 1.a
This is a paragraph that spans
multiple lines without bullet points.
"""
        sections = parse_markdown(md)
        assert len(sections[0]["cards"]) == 1
        assert "paragraph that spans multiple lines" in sections[0]["cards"][0]


class TestFormatDetection:
    """Tests for auto-detection of heading format."""

    def test_detects_section_keyed(self):
        md = "- 1.2: Title\n\t- Bullet.\n"
        sections = parse_markdown(md)
        assert sections[0]["section_id"] == "1.2"

    def test_detects_los_keyed(self):
        md = "### LOS 1.a\n- Bullet.\n"
        sections = parse_markdown(md)
        assert sections[0]["section_id"] == "1.a"

    def test_forced_format_section(self):
        md = "- 1.2: Title\n\t- Bullet.\n"
        sections = parse_markdown(md, format="section")
        assert sections[0]["section_id"] == "1.2"

    def test_forced_format_los(self):
        md = "### LOS 1.a\n- Bullet.\n"
        sections = parse_markdown(md, format="los")
        assert sections[0]["section_id"] == "1.a"

    def test_no_recognized_headings_raises(self):
        md = "Just some text without any section headings.\n"
        with pytest.raises(ValueError, match="No recognized section headings"):
            parse_markdown(md)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_md_importer.py -v`
Expected: FAIL — `md_importer` module not found

- [ ] **Step 3: Implement `parse_markdown` function**

Create `src/knowledge_base/srs/md_importer.py`:

```python
"""Markdown import pipeline for generation cards.

Parses structured markdown (section-keyed or LOS-keyed) into cards
and imports them into the generation_cards table.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from knowledge_base.srs.generation_db import init_generation_db, upsert_generation_card

DEFAULT_DB_PATH = Path("data/srs.db")

# ---------------------------------------------------------------------------
# Heading patterns
# ---------------------------------------------------------------------------

# Section-keyed: "- 1.2: Title", "## 1.2: Title", "### 1.2 Title"
_SECTION_RE = re.compile(
    r"^(?:-\s+|#{1,4}\s+)"       # leading dash+space or markdown heading
    r"(\d+\.\d+)"                 # section number (e.g., 1.2)
    r"[:\s]\s*"                   # colon or space separator
    r"(.+)$"                      # title text
)

# LOS-keyed: "### LOS 1.a", "### LOS 12.b"
_LOS_RE = re.compile(
    r"^#{1,4}\s+LOS\s+"          # heading with "LOS" keyword
    r"(\d+\.[a-z]+)"             # LOS identifier (e.g., 1.a)
    r"\s*$"                       # optional trailing whitespace
)

# Bullet line: starts with "- " or "\t- " (top-level) or deeper indent (sub-bullet)
_BULLET_RE = re.compile(r"^(\t*)- (.+)$")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_markdown(
    text: str,
    format: str | None = None,
) -> list[dict]:
    """Parse structured markdown into sections with cards.

    Parameters
    ----------
    text:
        Raw markdown text.
    format:
        Force heading format: ``"section"`` or ``"los"``. Auto-detected if None.

    Returns
    -------
    list[dict]
        Each dict has keys: ``section_id``, ``section_title``, ``cards``
        (list of strings).

    Raises
    ------
    ValueError
        If no recognized section headings are found.
    """
    lines = text.splitlines()

    # Detect format if not forced
    if format is None:
        format = _detect_format(lines)
        if format is None:
            raise ValueError(
                "No recognized section headings found. "
                "Use --format section|los to force interpretation."
            )

    sections: list[dict] = []
    current_section: dict | None = None

    for line in lines:
        heading = _try_parse_heading(line, format)
        if heading is not None:
            if current_section is not None:
                sections.append(current_section)
            current_section = {
                "section_id": heading["section_id"],
                "section_title": heading["section_title"],
                "cards": [],
            }
            continue

        if current_section is None:
            continue  # Skip content before first heading

        _accumulate_content(current_section, line, format)

    if current_section is not None:
        sections.append(current_section)

    # Finalize cards: join any pending paragraph lines
    for section in sections:
        section["cards"] = _finalize_cards(section["cards"])

    # Remove empty sections
    sections = [s for s in sections if s["cards"]]

    return sections


def _detect_format(lines: list[str]) -> str | None:
    """Scan lines to detect heading format. Returns 'section', 'los', or None."""
    for line in lines:
        if _LOS_RE.match(line):
            return "los"
        if _SECTION_RE.match(line):
            return "section"
    return None


def _try_parse_heading(line: str, format: str) -> dict | None:
    """Try to parse a line as a section heading. Returns dict or None."""
    if format == "los":
        m = _LOS_RE.match(line)
        if m:
            return {"section_id": m.group(1), "section_title": None}
    elif format == "section":
        m = _SECTION_RE.match(line)
        if m:
            return {"section_id": m.group(1), "section_title": m.group(2).strip()}
    return None


def _accumulate_content(section: dict, line: str, format: str) -> None:
    """Add a content line to the current section's card list.

    For section-keyed format, top-level bullets (tab-indented under the dash
    heading) become cards; sub-bullets fold into the parent.
    For LOS-keyed format, top-level bullets (no tab indent) become cards;
    indented lines fold into the parent.
    """
    if not line.strip():
        return

    bullet_match = _BULLET_RE.match(line)

    if format == "section":
        # In section-keyed, bullets under the heading are tab-indented
        if bullet_match:
            indent_level = len(bullet_match.group(1))
            text = bullet_match.group(2).strip()
            if indent_level <= 1:
                # Top-level bullet (one tab) = new card
                section["cards"].append(text)
            else:
                # Sub-bullet = fold into last card
                if section["cards"]:
                    section["cards"][-1] += " " + text
        else:
            # Non-bullet text: fold into last card or start new
            stripped = line.strip()
            if stripped:
                if section["cards"]:
                    section["cards"][-1] += " " + stripped
                else:
                    section["cards"].append(stripped)
    elif format == "los":
        if bullet_match:
            indent_level = len(bullet_match.group(1))
            text = bullet_match.group(2).strip()
            if indent_level == 0:
                # Top-level bullet = new card
                section["cards"].append(text)
            else:
                # Sub-bullet = fold into last card
                if section["cards"]:
                    section["cards"][-1] += " " + text
        else:
            # Non-bullet text: paragraph mode
            stripped = line.strip()
            if stripped:
                # Mark as paragraph (will be joined in finalize)
                section["cards"].append(("_para", stripped))


def _finalize_cards(cards: list) -> list[str]:
    """Join consecutive paragraph markers into single cards."""
    result: list[str] = []
    for item in cards:
        if isinstance(item, tuple) and item[0] == "_para":
            if result and isinstance(cards[cards.index(item) - 1], tuple):
                result[-1] += " " + item[1]
            else:
                result.append(item[1])
        else:
            result.append(item)
    return result
```

- [ ] **Step 4: Run parser tests**

Run: `uv run pytest tests/test_md_importer.py -v`
Expected: All tests PASS. If any fail, fix the parser logic and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/md_importer.py tests/test_md_importer.py
git commit -m "feat: add markdown parser for section-keyed and LOS-keyed formats

Auto-detects heading convention, splits bullets into cards,
folds sub-bullets into parents, skips preamble content."
```

---

### Task 4: Markdown Import CLI and DB Integration

**Files:**
- Modify: `src/knowledge_base/srs/md_importer.py`
- Modify: `pyproject.toml`
- Test: `tests/test_md_importer.py`

- [ ] **Step 1: Write failing tests for import-to-DB flow**

Add to `tests/test_md_importer.py`:

```python
from knowledge_base.srs.generation_db import init_generation_db, get_cards_by_source
from knowledge_base.srs.md_importer import parse_markdown, import_markdown


class TestImportMarkdown:
    """Tests for importing parsed markdown into the database."""

    OFFICIAL_MD = """\
- 1.2: Interest Rates and Time Value of Money
\t- An interest rate can have three interpretations.
\t- The nominal risk-free rate includes inflation.
- 1.3: Rates of Return
\t- Holding period return measures return over a specific period.
"""

    def test_import_creates_cards_in_db(self):
        conn = init_generation_db()
        count = import_markdown(
            conn,
            text=self.OFFICIAL_MD,
            deck="cfa_level1",
            topic_id="1",
            source="official",
        )
        assert count == 3
        cards = get_cards_by_source(conn, source="official", deck="cfa_level1")
        assert len(cards) == 3

    def test_import_sets_correct_fields(self):
        conn = init_generation_db()
        import_markdown(
            conn,
            text=self.OFFICIAL_MD,
            deck="cfa_level1",
            topic_id="1",
            source="official",
        )
        cards = get_cards_by_source(
            conn, source="official", section_ids=["1.2"], deck="cfa_level1"
        )
        # Sort by card_index for deterministic order
        cards.sort(key=lambda c: c["card_index"])
        assert len(cards) == 2
        assert cards[0]["section_id"] == "1.2"
        assert cards[0]["section_title"] == "Interest Rates and Time Value of Money"
        assert cards[0]["card_index"] == 0
        assert cards[0]["topic_id"] == "1"
        assert cards[0]["source"] == "official"
        assert cards[1]["card_index"] == 1

    def test_import_generates_question_with_section_context(self):
        conn = init_generation_db()
        import_markdown(
            conn,
            text=self.OFFICIAL_MD,
            deck="cfa_level1",
            topic_id="1",
            source="official",
        )
        cards = get_cards_by_source(
            conn, source="official", section_ids=["1.2"], deck="cfa_level1"
        )
        cards.sort(key=lambda c: c["card_index"])
        assert "1.2" in cards[0]["question"]
        assert "Interest Rates" in cards[0]["question"]

    def test_import_is_idempotent(self):
        conn = init_generation_db()
        import_markdown(conn, text=self.OFFICIAL_MD, deck="cfa_level1", topic_id="1", source="official")
        import_markdown(conn, text=self.OFFICIAL_MD, deck="cfa_level1", topic_id="1", source="official")
        cards = get_cards_by_source(conn, source="official", deck="cfa_level1")
        assert len(cards) == 3  # No duplicates

    def test_import_adds_source_tag(self):
        conn = init_generation_db()
        import_markdown(conn, text=self.OFFICIAL_MD, deck="cfa_level1", topic_id="1", source="official")
        cards = get_cards_by_source(conn, source="official", deck="cfa_level1")
        import json
        tags = json.loads(cards[0]["tags"])
        assert "source::official" in tags
        assert "reading::1" in tags
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_md_importer.py::TestImportMarkdown -v`
Expected: FAIL — `import_markdown` not defined

- [ ] **Step 3: Implement `import_markdown` function**

Add to `md_importer.py`:

```python
import json


def import_markdown(
    conn: sqlite3.Connection,
    text: str,
    deck: str,
    topic_id: str,
    source: str,
    format: str | None = None,
) -> int:
    """Parse markdown and upsert cards into the generation_cards table.

    Parameters
    ----------
    conn:
        SQLite connection with generation schema initialised.
    text:
        Raw markdown text to parse.
    deck:
        Deck name (e.g., "cfa_level1").
    topic_id:
        Topic/reading number as string (e.g., "1").
    source:
        Source identifier (e.g., "official", "schweser").
    format:
        Force heading format. Auto-detected if None.

    Returns
    -------
    int
        Number of cards upserted.
    """
    sections = parse_markdown(text, format=format)

    tags = json.dumps([
        f"reading::{topic_id}",
        f"source::{source}",
    ])

    count = 0
    for section in sections:
        section_id = section["section_id"]
        section_title = section["section_title"]

        for card_index, card_text in enumerate(section["cards"]):
            if section_title:
                question = f"{section_id}: {section_title} [{card_index + 1}/{len(section['cards'])}]"
            else:
                question = f"LOS {section_id} [{card_index + 1}/{len(section['cards'])}]"

            upsert_generation_card(conn, {
                "deck": deck,
                "topic_id": topic_id,
                "source": source,
                "section_id": section_id,
                "section_title": section_title,
                "card_index": card_index,
                "question": question,
                "answer": card_text,
                "tags": tags,
            })
            count += 1

    return count
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_md_importer.py::TestImportMarkdown -v`
Expected: All tests PASS

- [ ] **Step 5: Add CLI entry point**

Add the `main` function to `md_importer.py`:

```python
def main() -> None:
    """CLI entry point: import markdown study material into generation_cards."""
    parser = argparse.ArgumentParser(
        description="Import structured markdown into generation_cards table"
    )
    parser.add_argument("file", help="Path to the markdown file")
    parser.add_argument("--deck", required=True, help="Deck name (e.g., cfa_level1)")
    parser.add_argument("--topic", required=True, help="Topic/reading number (e.g., 1)")
    parser.add_argument("--source", required=True, help="Source identifier (e.g., official, schweser)")
    parser.add_argument("--format", choices=["section", "los"], default=None,
                        help="Force heading format (auto-detected if omitted)")
    parser.add_argument("--preview", action="store_true",
                        help="Print parsed sections and card counts without writing to DB")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH),
                        help=f"Database path (default: {DEFAULT_DB_PATH})")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        raise SystemExit(1)

    text = file_path.read_text()

    if args.preview:
        sections = parse_markdown(text, format=args.format)
        total = 0
        for section in sections:
            n = len(section["cards"])
            total += n
            title = f": {section['section_title']}" if section["section_title"] else ""
            print(f"  {section['section_id']}{title} ({n} cards)")
        print(f"\nTotal: {total} cards across {len(sections)} sections")
        return

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_generation_db(db_path=str(db_path))

    count = import_markdown(
        conn, text=text, deck=args.deck, topic_id=args.topic,
        source=args.source, format=args.format,
    )
    print(f"Imported {count} cards into {db_path} (deck={args.deck}, topic={args.topic}, source={args.source})")
```

- [ ] **Step 6: Add script entry point to pyproject.toml**

Add to the `[project.scripts]` section in `pyproject.toml`:

```toml
gen-import-md = "knowledge_base.srs.md_importer:main"
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/knowledge_base/srs/md_importer.py tests/test_md_importer.py pyproject.toml
git commit -m "feat: add gen-import-md CLI for markdown study material import

Parses section-keyed and LOS-keyed markdown into generation cards.
Supports --preview mode and idempotent upsert."
```

---

### Task 5: Catalog TUI — Tree Builder and Selection Logic

**Files:**
- Create: `src/knowledge_base/srs/catalog.py`
- Create: `tests/test_catalog.py`

- [ ] **Step 1: Write failing tests for tree building**

Create `tests/test_catalog.py`:

```python
"""Tests for srs/catalog.py — catalog tree builder and selection logic."""

import pytest

from knowledge_base.srs.generation_db import init_generation_db, insert_generation_card
from knowledge_base.srs.catalog import build_tree, CatalogNode


class TestBuildTree:
    """Tests for building the catalog tree from DB data."""

    def _populate(self, conn):
        cards = [
            {"deck": "cfa_level1", "topic_id": "1", "source": "los", "section_id": "1.a", "card_index": 0,
             "question": "Q", "answer": "A", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "los", "section_id": "1.b", "card_index": 0,
             "question": "Q", "answer": "A", "tags": "[]"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "official", "section_id": "1.2", "card_index": 0,
             "question": "Q", "answer": "A", "tags": "[]", "section_title": "Interest Rates and TVM"},
            {"deck": "cfa_level1", "topic_id": "1", "source": "official", "section_id": "1.2", "card_index": 1,
             "question": "Q", "answer": "A", "tags": "[]", "section_title": "Interest Rates and TVM"},
            {"deck": "cfa_level1", "topic_id": "2", "source": "los", "section_id": "2.a", "card_index": 0,
             "question": "Q", "answer": "A", "tags": "[]"},
        ]
        for c in cards:
            insert_generation_card(conn, c)

    def test_tree_has_deck_at_root(self):
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        assert len(roots) == 1
        assert roots[0].label == "cfa_level1"
        assert roots[0].node_type == "deck"

    def test_topics_under_deck(self):
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        topics = roots[0].children
        topic_ids = [t.topic_id for t in topics]
        assert "1" in topic_ids
        assert "2" in topic_ids

    def test_sources_under_topic(self):
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        topic_1 = [t for t in roots[0].children if t.topic_id == "1"][0]
        sources = [s.source for s in topic_1.children]
        assert "los" in sources
        assert "official" in sources

    def test_sections_under_multi_card_source(self):
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        topic_1 = [t for t in roots[0].children if t.topic_id == "1"][0]
        official = [s for s in topic_1.children if s.source == "official"][0]
        assert len(official.children) == 1  # one section: 1.2
        assert official.children[0].section_id == "1.2"
        assert official.children[0].card_count == 2

    def test_los_source_is_leaf(self):
        """LOS source (one card per section) should not expand into sections."""
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        topic_1 = [t for t in roots[0].children if t.topic_id == "1"][0]
        los = [s for s in topic_1.children if s.source == "los"][0]
        assert los.card_count == 2
        assert len(los.children) == 0  # LOS is leaf

    def test_card_count_propagation(self):
        conn = init_generation_db()
        self._populate(conn)
        roots = build_tree(conn)
        assert roots[0].card_count == 5  # total


class TestCatalogNodeSelection:
    """Tests for selection logic on CatalogNode."""

    def test_select_parent_selects_children(self):
        root = CatalogNode(label="deck", node_type="deck", card_count=5)
        child = CatalogNode(label="topic", node_type="topic", card_count=3)
        root.children.append(child)
        root.set_selected(True)
        assert child.selected is True

    def test_deselect_parent_deselects_children(self):
        root = CatalogNode(label="deck", node_type="deck", card_count=5)
        child = CatalogNode(label="topic", node_type="topic", card_count=3)
        root.children.append(child)
        root.set_selected(True)
        root.set_selected(False)
        assert child.selected is False

    def test_collect_selected_card_ids(self):
        conn = init_generation_db()
        insert_generation_card(conn, {
            "deck": "d", "topic_id": "1", "source": "los", "section_id": "1.a",
            "card_index": 0, "question": "Q", "answer": "A", "tags": "[]",
        })
        roots = build_tree(conn)
        roots[0].set_selected(True)
        card_ids = roots[0].collect_selected_card_ids()
        assert len(card_ids) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog.py -v`
Expected: FAIL — `catalog` module not found

- [ ] **Step 3: Implement `CatalogNode` and `build_tree`**

Create `src/knowledge_base/srs/catalog.py`:

```python
"""Catalog tree builder and selection logic for generation cards.

Builds a navigable tree from the generation_cards table, grouped by
deck → topic → source → section. Supports multi-select at any level.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from knowledge_base.srs.generation_db import get_catalog_tree


@dataclass
class CatalogNode:
    """A node in the catalog tree with selection state."""

    label: str
    node_type: str  # "deck", "topic", "source", "section"
    card_count: int = 0
    children: list[CatalogNode] = field(default_factory=list)
    selected: bool = False

    # Optional identifiers for filtering
    deck: str | None = None
    topic_id: str | None = None
    source: str | None = None
    section_id: str | None = None
    section_title: str | None = None

    # Card IDs at leaf level (populated for leaf nodes)
    _card_ids: list[int] = field(default_factory=list)

    def set_selected(self, value: bool) -> None:
        """Set selection state, propagating to all children."""
        self.selected = value
        for child in self.children:
            child.set_selected(value)

    def collect_selected_card_ids(self) -> list[int]:
        """Collect card_ids from all selected leaf nodes in this subtree."""
        if not self.children:
            return list(self._card_ids) if self.selected else []
        result: list[int] = []
        for child in self.children:
            result.extend(child.collect_selected_card_ids())
        return result


def build_tree(
    conn: sqlite3.Connection,
    deck: str | None = None,
) -> list[CatalogNode]:
    """Build catalog tree from the database.

    Returns a list of deck-level root nodes. Each node contains
    children down to the source or section level.
    """
    rows = get_catalog_tree(conn, deck=deck)

    # Also fetch card_ids for leaf-level mapping
    all_cards = conn.execute(
        "SELECT card_id, deck, topic_id, source, section_id FROM generation_cards"
    ).fetchall()
    card_id_map: dict[tuple, list[int]] = {}
    for card in all_cards:
        key = (card[1], card[2], card[3], card[4])  # deck, topic_id, source, section_id
        card_id_map.setdefault(key, []).append(card[0])

    # Group rows into tree structure
    decks: dict[str, CatalogNode] = {}

    for row in rows:
        d = row["deck"]
        tid = row["topic_id"]
        src = row["source"]
        sid = row["section_id"]
        stitle = row["section_title"]
        count = row["card_count"]

        # Deck level
        if d not in decks:
            decks[d] = CatalogNode(label=d, node_type="deck", deck=d)

        deck_node = decks[d]

        # Topic level
        topic_node = None
        for t in deck_node.children:
            if t.topic_id == tid:
                topic_node = t
                break
        if topic_node is None:
            topic_node = CatalogNode(
                label=f"Reading {tid}", node_type="topic",
                deck=d, topic_id=tid,
            )
            deck_node.children.append(topic_node)

        # Source level
        source_node = None
        for s in topic_node.children:
            if s.source == src:
                source_node = s
                break
        if source_node is None:
            source_node = CatalogNode(
                label=src.title(), node_type="source",
                deck=d, topic_id=tid, source=src,
            )
            topic_node.children.append(source_node)

        # For LOS source (1 card per section), accumulate at source level (leaf)
        # For multi-card sources, create section children
        if count == 1 and src == "los":
            source_node.card_count += count
            cids = card_id_map.get((d, tid, src, sid), [])
            source_node._card_ids.extend(cids)
        else:
            title_display = f"{sid}: {stitle}" if stitle else f"LOS {sid}"
            section_node = CatalogNode(
                label=f"{title_display} ({count})", node_type="section",
                card_count=count, deck=d, topic_id=tid, source=src,
                section_id=sid, section_title=stitle,
                _card_ids=card_id_map.get((d, tid, src, sid), []),
            )
            source_node.children.append(section_node)
            source_node.card_count += count

        topic_node.card_count = sum(s.card_count for s in topic_node.children)
        deck_node.card_count = sum(t.card_count for t in deck_node.children)

    return list(decks.values())
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/catalog.py tests/test_catalog.py
git commit -m "feat: add catalog tree builder with multi-select support

Builds deck → topic → source → section hierarchy from DB.
LOS sources are leaf nodes; multi-card sources expand to sections."
```

---

### Task 6: Catalog TUI Screen (Textual Widget)

**Files:**
- Modify: `src/knowledge_base/srs/catalog.py`
- Modify: `src/knowledge_base/srs/generation_tui.py`

- [ ] **Step 1: Add Textual Tree widget to catalog.py**

Add imports and the catalog screen class to `catalog.py`:

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Tree, Footer, Header, Static
from textual.binding import Binding


class CatalogScreen(Screen):
    """Browsable catalog of generation card material."""

    BINDINGS = [
        Binding("m", "launch_massed", "Massed Practice"),
        Binding("o", "launch_ordered", "Ordered Practice"),
        Binding("p", "launch_paste", "Paste & Drill"),
        Binding("q", "quit_catalog", "Quit"),
        Binding("space", "toggle_select", "Select", show=False),
    ]

    def __init__(self, conn: sqlite3.Connection, deck: str | None = None) -> None:
        super().__init__()
        self.conn = conn
        self.deck_filter = deck
        self.roots: list[CatalogNode] = []
        self._selected_count = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tree("Generation Card Catalog", id="catalog-tree")
        yield Static("0 cards selected", id="selection-count")
        yield Footer()

    def on_mount(self) -> None:
        self.roots = build_tree(self.conn, deck=self.deck_filter)
        tree = self.query_one("#catalog-tree", Tree)
        tree.root.expand()
        for deck_node in self.roots:
            self._add_node(tree.root, deck_node)

    def _add_node(self, parent, catalog_node: CatalogNode) -> None:
        """Recursively add CatalogNode to the Textual Tree."""
        count_suffix = f" ({catalog_node.card_count})" if catalog_node.card_count else ""
        label = f"{catalog_node.label}{count_suffix}"
        if catalog_node.children:
            branch = parent.add(label, data=catalog_node)
            for child in catalog_node.children:
                self._add_node(branch, child)
        else:
            parent.add_leaf(label, data=catalog_node)

    def _update_selection_count(self) -> None:
        total = sum(r.collect_selected_card_ids() for r in self.roots, [])
        count = len(set(total))
        self._selected_count = count
        self.query_one("#selection-count", Static).update(f"{count} cards selected")

    def action_toggle_select(self) -> None:
        tree = self.query_one("#catalog-tree", Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return
        catalog_node: CatalogNode = node.data
        catalog_node.set_selected(not catalog_node.selected)
        # Update visual indicators
        self._refresh_labels(tree.root)
        self._update_selection_count()

    def _refresh_labels(self, tree_node) -> None:
        """Update tree node labels to show selection state."""
        if tree_node.data is not None:
            catalog_node: CatalogNode = tree_node.data
            count_suffix = f" ({catalog_node.card_count})" if catalog_node.card_count else ""
            marker = "[x] " if catalog_node.selected else "[ ] "
            tree_node.set_label(f"{marker}{catalog_node.label}{count_suffix}")
        for child in tree_node.children:
            self._refresh_labels(child)

    def _get_selected_card_ids(self) -> list[int]:
        """Collect all selected card IDs across all roots."""
        result: list[int] = []
        for root in self.roots:
            result.extend(root.collect_selected_card_ids())
        return list(set(result))

    def action_launch_massed(self) -> None:
        card_ids = self._get_selected_card_ids()
        if card_ids:
            self.dismiss(("massed", card_ids))

    def action_launch_ordered(self) -> None:
        card_ids = self._get_selected_card_ids()
        if card_ids:
            self.dismiss(("ordered", card_ids))

    def action_launch_paste(self) -> None:
        self.dismiss(("paste", []))

    def action_quit_catalog(self) -> None:
        self.app.exit()
```

- [ ] **Step 2: Add `get_cards_by_ids` to `generation_db.py`**

Add a function to load cards by their IDs (needed when catalog passes selected IDs to practice):

```python
def get_cards_by_ids(
    conn: sqlite3.Connection,
    card_ids: list[int],
) -> list[dict]:
    """Return cards matching the given card_ids."""
    if not card_ids:
        return []
    placeholders = ", ".join("?" * len(card_ids))
    sql = f"SELECT * FROM generation_cards WHERE card_id IN ({placeholders})"
    rows = conn.execute(sql, card_ids).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 3: Integrate catalog into `generation_tui.py`**

In `generation_tui.py`, update `main()` to show the catalog when no practice flags are provided and add new CLI flags. Key changes:

Add new imports at the top:

```python
from knowledge_base.srs.catalog import CatalogScreen
from knowledge_base.srs.generation_db import get_cards_by_ids
```

Add new argparse flags in `main()` after the existing ones:

```python
    parser.add_argument("--source", default=None,
                        help="Filter by source (e.g., official, schweser, los)")
    parser.add_argument("--topic", default=None,
                        help="Filter by topic/reading (e.g., 1, 1-5, 1,3,5)")
    parser.add_argument("--section", default=None,
                        help="Filter by section (e.g., 1.2, 1.a-1.c)")
    parser.add_argument("--paste", action="store_true",
                        help="Paste text for ephemeral practice")
    parser.add_argument("--save-as", default=None,
                        help="Save pasted text to DB with this label")
    parser.add_argument("--split-by", choices=["sentence", "line"], default="sentence",
                        help="How to split pasted text (default: sentence)")
```

Update the app creation logic to handle catalog mode. When no practice/ordered-practice/paste/stats flags are present, launch the `CatalogScreen` first, then use its result to configure the practice session.

Pass the new `source`/`section` args through to the app so they can be used as CLI shortcuts for filtering.

- [ ] **Step 4: Manually test the catalog**

Run: `uv run review-gen` (with cards in the DB)
Expected: Catalog screen appears with tree browser. Navigate with arrow keys, select with Space, launch with `m` or `o`.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/catalog.py src/knowledge_base/srs/generation_db.py src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add catalog TUI screen as default entry point for review-gen

Tree browser with deck → topic → source → section hierarchy.
Multi-select with Space, launch massed (m) or ordered (o) practice.
New CLI flags: --source, --topic, --section, --paste, --save-as."
```

---

### Task 7: Paste-and-Drill Mode

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`
- Create: `tests/test_paste_drill.py`

- [ ] **Step 1: Write failing tests for text splitting**

Create `tests/test_paste_drill.py`:

```python
"""Tests for paste-and-drill text splitting."""

import pytest

from knowledge_base.srs.generation_tui import split_paste_text


class TestSplitPasteText:
    def test_split_by_sentence(self):
        text = "First sentence. Second sentence. Third sentence."
        cards = split_paste_text(text, split_by="sentence")
        assert len(cards) == 3
        assert cards[0] == "First sentence."
        assert cards[1] == "Second sentence."
        assert cards[2] == "Third sentence."

    def test_split_by_line(self):
        text = "Line one\nLine two\nLine three"
        cards = split_paste_text(text, split_by="line")
        assert len(cards) == 3

    def test_split_by_sentence_handles_abbreviations(self):
        text = "The U.S. economy grew. Exports increased."
        cards = split_paste_text(text, split_by="sentence")
        # Should handle this reasonably (at least 2 cards)
        assert len(cards) >= 2

    def test_empty_lines_skipped(self):
        text = "Line one\n\n\nLine two"
        cards = split_paste_text(text, split_by="line")
        assert len(cards) == 2

    def test_empty_input(self):
        cards = split_paste_text("", split_by="sentence")
        assert len(cards) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_paste_drill.py -v`
Expected: FAIL — `split_paste_text` not defined

- [ ] **Step 3: Implement `split_paste_text`**

Add to `generation_tui.py`:

```python
import re as _re


def split_paste_text(text: str, split_by: str = "sentence") -> list[str]:
    """Split raw text into card-sized chunks.

    Parameters
    ----------
    text:
        Raw input text.
    split_by:
        ``"sentence"`` splits on sentence boundaries (period + space/newline).
        ``"line"`` splits on newlines.
    """
    if not text.strip():
        return []

    if split_by == "line":
        return [line.strip() for line in text.splitlines() if line.strip()]

    # Sentence splitting: split on ". " or ".\n" but not abbreviations
    # Simple heuristic: split on period followed by space and uppercase letter,
    # or period at end of string
    sentences = _re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    return [s.strip() for s in sentences if s.strip()]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_paste_drill.py -v`
Expected: All tests PASS

- [ ] **Step 5: Integrate paste mode into the TUI**

In `generation_tui.py`, add paste handling in the `main()` function. When `--paste` is provided:

1. Read text from stdin if piped, otherwise prompt with `input()` in a loop (enter blank line to finish)
2. Split with `split_paste_text`
3. Build ephemeral card dicts (no card_id, no DB writes) with sequential `card_index`
4. Launch ordered practice with those cards

When `--save-as` is also provided (with `--deck`, `--topic`, `--source`):

1. After splitting, call `import_markdown` or directly upsert cards into DB
2. Then launch practice as normal

Add this logic before the app creation in `main()`:

```python
    if args.paste:
        import sys
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("Paste text below (blank line to finish):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            text = "\n".join(lines)

        card_texts = split_paste_text(text, split_by=args.split_by)
        if not card_texts:
            print("No cards generated from input.")
            return

        if args.save_as and args.deck and args.topic and args.source:
            from knowledge_base.srs.md_importer import import_markdown
            # Wrap as simple text (one card per line, no sections)
            # Import directly as individual cards under a single section
            for i, card_text in enumerate(card_texts):
                upsert_generation_card(conn, {
                    "deck": args.deck,
                    "topic_id": args.topic,
                    "source": args.source,
                    "section_id": args.save_as,
                    "section_title": args.save_as,
                    "card_index": i,
                    "question": f"{args.save_as} [{i + 1}/{len(card_texts)}]",
                    "answer": card_text,
                    "tags": json.dumps([f"reading::{args.topic}", f"source::{args.source}"]),
                })
            print(f"Saved {len(card_texts)} cards as \"{args.save_as}\"")

        # Build ephemeral cards for practice
        cards = []
        for i, card_text in enumerate(card_texts):
            cards.append({
                "card_id": -(i + 1),  # negative IDs = ephemeral
                "deck": args.deck or "paste",
                "topic_id": args.topic or "0",
                "source": "paste",
                "section_id": "paste",
                "section_title": None,
                "card_index": i,
                "question": f"[{i + 1}/{len(card_texts)}]",
                "answer": card_text,
                "tags": "[]",
                "masking_level": 0,
                "phase": "generation",
                "consecutive_max_passes": 0,
            })

        # Launch ordered practice with ephemeral cards
        # Pass cards directly to the app instead of loading from DB
```

Update the `GenerationReviewApp` to accept pre-built cards for paste mode. Add a `paste_cards` parameter to `__init__` and use it in `_build_ordered_practice_queue` when present.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py tests/test_paste_drill.py
git commit -m "feat: add paste-and-drill mode for ephemeral text practice

--paste reads from stdin or interactive input, splits into cards,
and launches ordered practice. --save-as persists to DB."
```

---

### Task 8: Update Practice Session Headers

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py:372-408`

- [ ] **Step 1: Update header display to include source context**

In `generation_tui.py`, update the `_show_generation_card` method's header formatting. Replace the header construction (around lines 377-399) with logic that checks for source:

```python
        # Build header
        section_id = card["section_id"]
        source = card.get("source", "los")
        section_title = card.get("section_title")

        if source == "los":
            # Unchanged from current: deck > section_id
            location = f"{deck} > {section_id}"
        elif section_title:
            # Elaboration with title: deck > source > section_id: title
            location = f"{deck} > {source} > {section_id}: {section_title}"
        else:
            # Elaboration without title (e.g., Schweser): deck > source > LOS section_id
            location = f"{deck} > {source} > LOS {section_id}"
```

Do the same for `_show_recall_card` header formatting.

- [ ] **Step 2: Update `_section_sort_key` for multi-source ordering**

The renamed `_section_sort_key` (formerly `_los_sort_key`) should handle section IDs from both formats:

```python
def _section_sort_key(card: dict) -> tuple[str, int, str, int]:
    """Sort key for natural ordering across sources: (source, reading, suffix, card_index)."""
    section_id = card["section_id"]
    source = card.get("source", "los")
    card_index = card.get("card_index", 0)
    parts = section_id.split(".", 1)
    try:
        reading_num = int(parts[0])
    except ValueError:
        reading_num = 0
    suffix = parts[1] if len(parts) > 1 else ""
    return (source, reading_num, suffix, card_index)
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "feat: update practice headers to show source and section context

LOS cards unchanged. Elaboration cards show: deck > source > section.
Sort key updated for multi-source ordering."
```

---

### Task 9: CLI Shortcut Flags for Source/Section Filtering

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`

- [ ] **Step 1: Wire `--source`/`--section` flags to practice modes**

In `generation_tui.py`, update the practice-mode loading logic. When `--practice` or `--ordered-practice` is used with `--source`, use `get_cards_by_source` instead of `get_cards_by_readings`:

```python
    # In _build_practice_queue / _build_ordered_practice_queue:
    if self.source_filter:
        from knowledge_base.srs.generation_db import get_cards_by_source
        cards = get_cards_by_source(
            self.conn,
            source=self.source_filter,
            topic_ids=topic_ids if topic_ids else None,
            section_ids=section_ids if section_ids else None,
            deck=self.deck,
        )
    else:
        # Existing behavior: filter by readings, implicitly source="los"
        cards = get_cards_by_readings(self.conn, topic_ids, deck=self.deck)
```

Pass `source_filter` and `section_filter` from `main()` args through to the app `__init__`.

Add `_parse_reading_spec` for section parsing too (it works on the same syntax: `1.2`, `1.2-1.4`, `1.a,1.b`).

- [ ] **Step 2: Ensure backwards compatibility**

When `--practice`/`--ordered-practice` is used WITHOUT `--source`, behavior is identical to today (implicitly `source="los"`). Verify by running:

Run: `uv run pytest -v`
Expected: All existing tests PASS unchanged

- [ ] **Step 3: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add --source and --section CLI flags for filtered practice

review-gen --source official --topic 1 --ordered-practice
drills Official Overview cards for Reading 1.
Without --source, defaults to los for backwards compatibility."
```

---

### Task 10: Update CLAUDE.md and Final Integration Test

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md quick reference and key constraints**

Add `gen-import-md` to the quick reference section and document the new CLI flags:

```markdown
# Generation cards (CFA LOS + multi-source)
uv run gen-import                       # import LOS → data/srs.db
uv run gen-import-md <file> --deck D --topic T --source S  # import markdown
uv run gen-import-md <file> ... --preview  # preview without importing
uv run review-gen                       # launch catalog TUI
uv run review-gen [deck]                # launch with deck filter
uv run review-gen --source S --topic T --ordered-practice  # source-filtered practice
uv run review-gen --paste               # paste text for ephemeral drill
uv run review-gen --paste --save-as N --deck D --topic T --source S  # persist pasted text
```

- [ ] **Step 2: Run full test suite one final time**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with gen-import-md and catalog TUI commands"
```
