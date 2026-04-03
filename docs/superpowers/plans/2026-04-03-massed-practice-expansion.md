# Massed Practice Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact-answer card type, CSV import, randomized massed practice reshuffling, numeric-aware answer matching, and per-card session pass counter.

**Architecture:** Add `card_type` column to `generation_cards` (schema v3 migration). New `csv_importer.py` for CSV import. Replace delay-based queue with positional-insertion queue in `generation_tui.py`. Add `check_exact_answer()` to `text_scoring.py`. TUI branches on card type for rendering and answer evaluation.

**Tech Stack:** Python 3.12, SQLite, textual, pytest

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `src/knowledge_base/srs/generation_db.py` | Schema, migrations, CRUD | Modify: add `card_type` column, v2→v3 migration |
| `src/knowledge_base/srs/csv_importer.py` | CSV import CLI and parsing | Create |
| `src/knowledge_base/srs/text_scoring.py` | Token comparison + numeric matching | Modify: add `check_exact_answer()` |
| `src/knowledge_base/srs/generation_tui.py` | TUI, queue, review flow | Modify: positional queue, exact-card branching, pass counter |
| `tests/test_generation_db.py` | DB schema and CRUD tests | Modify: add v3 migration + card_type tests |
| `tests/test_csv_importer.py` | CSV import tests | Create |
| `tests/test_text_scoring.py` | Scoring tests | Modify: add numeric matching tests |
| `tests/test_massed_practice.py` | Reshuffling algorithm tests | Create |
| `pyproject.toml` | Entry points | Modify: add `gen-import-csv` |

---

### Task 1: Schema v3 migration — add `card_type` column

**Files:**
- Modify: `src/knowledge_base/srs/generation_db.py`
- Modify: `tests/test_generation_db.py`

- [ ] **Step 1: Write failing tests for v3 migration**

Add to `tests/test_generation_db.py`:

```python
class TestSchemaV3Migration:
    """Tests for v2 → v3 migration adding card_type column."""

    def _make_v2_db(self, tmp_path):
        """Create a v2 database with some cards, return the path."""
        db_file = tmp_path / "v2.db"
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            CREATE TABLE generation_schema_version (
                version INTEGER NOT NULL
            )
        """)
        conn.execute("INSERT INTO generation_schema_version (version) VALUES (2)")
        conn.execute("""
            CREATE TABLE generation_cards (
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
        conn.execute("""
            INSERT INTO generation_cards (deck, topic_id, section_id, question, answer)
            VALUES ('test', '1', '1.a', 'Q?', 'A')
        """)
        conn.commit()
        conn.close()
        return db_file

    def test_migration_adds_card_type_column(self, tmp_path):
        db_file = self._make_v2_db(tmp_path)
        conn = init_generation_db(db_path=str(db_file))
        row = conn.execute(
            "SELECT card_type FROM generation_cards WHERE card_id = 1"
        ).fetchone()
        assert row["card_type"] == "masking"

    def test_migration_updates_schema_version(self, tmp_path):
        db_file = self._make_v2_db(tmp_path)
        conn = init_generation_db(db_path=str(db_file))
        version = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()[0]
        assert version == 3

    def test_migration_preserves_existing_cards(self, tmp_path):
        db_file = self._make_v2_db(tmp_path)
        conn = init_generation_db(db_path=str(db_file))
        card = conn.execute(
            "SELECT * FROM generation_cards WHERE card_id = 1"
        ).fetchone()
        assert card["question"] == "Q?"
        assert card["answer"] == "A"
        assert card["deck"] == "test"

    def test_fresh_db_has_card_type_column(self, tmp_path):
        db_file = tmp_path / "fresh.db"
        conn = init_generation_db(db_path=str(db_file))
        conn.execute("""
            INSERT INTO generation_cards
            (deck, topic_id, section_id, question, answer, card_type)
            VALUES ('d', '1', '1.a', 'Q', 'A', 'exact')
        """)
        conn.commit()
        row = conn.execute("SELECT card_type FROM generation_cards").fetchone()
        assert row["card_type"] == "exact"

    def test_insert_exact_card(self, tmp_path):
        db_file = tmp_path / "test.db"
        conn = init_generation_db(db_path=str(db_file))
        card_id = insert_generation_card(conn, {
            "deck": "indicators",
            "topic_id": "gdp",
            "section_id": "1",
            "card_index": 0,
            "question": "GDP per capita, US?",
            "answer": "63544",
            "card_type": "exact",
        })
        card = get_generation_card(conn, card_id)
        assert card["card_type"] == "exact"

    def test_default_card_type_is_masking(self, tmp_path):
        db_file = tmp_path / "test.db"
        conn = init_generation_db(db_path=str(db_file))
        card_id = insert_generation_card(conn, {
            "deck": "test",
            "topic_id": "1",
            "section_id": "1.a",
            "question": "Q?",
            "answer": "A",
        })
        card = get_generation_card(conn, card_id)
        assert card["card_type"] == "masking"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generation_db.py::TestSchemaV3Migration -v`
Expected: FAIL — no `card_type` column exists

- [ ] **Step 3: Implement v3 migration**

In `src/knowledge_base/srs/generation_db.py`:

1. Change `CURRENT_SCHEMA_VERSION = 2` → `CURRENT_SCHEMA_VERSION = 3`

2. Add `card_type` column to `_DDL_GENERATION_CARDS` after the `tags` line:
```python
    card_type              TEXT    NOT NULL DEFAULT 'masking',
```

3. Add `"card_type"` to `_CONTENT_FIELDS` tuple.

4. Add migration function:
```python
def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate generation_cards from schema v2 to v3: add card_type column."""
    conn.execute(
        "ALTER TABLE generation_cards ADD COLUMN card_type TEXT NOT NULL DEFAULT 'masking'"
    )
    conn.execute(
        "UPDATE generation_schema_version SET version = ?",
        (CURRENT_SCHEMA_VERSION,),
    )
```

5. In `init_generation_db`, update the migration check block. Change:
```python
            needs_migration = stored_version < 2
```
to:
```python
            needs_v1_migration = stored_version < 2
            needs_v3_migration = stored_version < 3
```

Update the migration block:
```python
    if needs_v1_migration:
        conn.execute("PRAGMA foreign_keys=OFF;")
        with conn:
            _migrate_v1_to_v2(conn)
        conn.execute("PRAGMA foreign_keys=ON;")

    if needs_v3_migration:
        with conn:
            _migrate_v2_to_v3(conn)
        conn.execute("PRAGMA foreign_keys=ON;")
    else:
        conn.execute("PRAGMA foreign_keys=ON;")
```

Note: The v2→v3 migration is a simple `ALTER TABLE ADD COLUMN` which SQLite supports without table recreation. No need to disable foreign keys.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_generation_db.py -v`
Expected: All tests pass including new TestSchemaV3Migration tests

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/generation_db.py tests/test_generation_db.py
git commit -m "feat: add card_type column to generation_cards (schema v3)"
```

---

### Task 2: Numeric-aware answer matching

**Files:**
- Modify: `src/knowledge_base/srs/text_scoring.py`
- Modify: `tests/test_text_scoring.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_text_scoring.py`:

```python
from knowledge_base.srs.text_scoring import check_exact_answer


class TestCheckExactAnswer:
    """Tests for numeric-aware exact answer matching."""

    def test_exact_string_match(self):
        assert check_exact_answer("hello", "hello") is True

    def test_case_insensitive_string(self):
        assert check_exact_answer("Yes", "yes") is True

    def test_string_mismatch(self):
        assert check_exact_answer("hello", "world") is False

    def test_numeric_match_integers(self):
        assert check_exact_answer("1234", "1234") is True

    def test_numeric_match_with_commas(self):
        assert check_exact_answer("1234", "1,234") is True

    def test_numeric_match_trailing_zeros(self):
        assert check_exact_answer("6.20", "6.2") is True

    def test_numeric_match_float(self):
        assert check_exact_answer("3.14", "3.14") is True

    def test_numeric_mismatch(self):
        assert check_exact_answer("6.3", "6.2") is False

    def test_whitespace_stripped(self):
        assert check_exact_answer("  6.2  ", "6.2") is True

    def test_dollar_sign_prevents_numeric_parse(self):
        assert check_exact_answer("$6.2", "6.2") is False

    def test_both_non_numeric_case_insensitive(self):
        assert check_exact_answer("YES", "yes") is True

    def test_empty_strings_match(self):
        assert check_exact_answer("", "") is True

    def test_comma_in_typed_and_stored(self):
        assert check_exact_answer("1,234", "1,234") is True

    def test_integer_vs_float_representation(self):
        assert check_exact_answer("100", "100.0") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_text_scoring.py::TestCheckExactAnswer -v`
Expected: FAIL — `check_exact_answer` not defined

- [ ] **Step 3: Implement `check_exact_answer`**

Add to `src/knowledge_base/srs/text_scoring.py`:

```python
def _try_parse_number(s: str) -> float | None:
    """Try to parse a string as a number, removing commas. Returns None on failure."""
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def check_exact_answer(typed: str, stored: str) -> bool:
    """Check if typed answer matches stored answer.

    Numeric-aware: both sides are parsed as numbers if possible,
    compared as floats. Falls back to case-insensitive string comparison.
    """
    typed = typed.strip()
    stored = stored.strip()

    typed_num = _try_parse_number(typed)
    stored_num = _try_parse_number(stored)

    if typed_num is not None and stored_num is not None:
        return typed_num == stored_num

    return typed.lower() == stored.lower()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_text_scoring.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/text_scoring.py tests/test_text_scoring.py
git commit -m "feat: add numeric-aware exact answer matching"
```

---

### Task 3: CSV importer

**Files:**
- Create: `src/knowledge_base/srs/csv_importer.py`
- Create: `tests/test_csv_importer.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing tests**

Create `tests/test_csv_importer.py`:

```python
"""Tests for CSV import of exact-answer cards."""

import csv
import io
from pathlib import Path

import pytest

from knowledge_base.srs.csv_importer import parse_csv, import_csv
from knowledge_base.srs.generation_db import (
    init_generation_db,
    get_generation_card,
)


def _write_csv(tmp_path, filename, rows, fieldnames=None):
    """Write rows to a CSV file and return the path."""
    path = tmp_path / filename
    if fieldnames is None:
        fieldnames = rows[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestParseCsv:
    def test_basic_parse(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "What is X?", "answer": "42"},
            {"question": "What is Y?", "answer": "7.5"},
        ])
        cards = parse_csv(path, deck="test", source="src", topic="t")
        assert len(cards) == 2
        assert cards[0]["question"] == "What is X?"
        assert cards[0]["answer"] == "42"

    def test_card_type_is_exact(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["card_type"] == "exact"

    def test_card_index_auto_assigned(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"},
            {"question": "Q3?", "answer": "A3"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert [c["card_index"] for c in cards] == [0, 1, 2]

    def test_topic_from_csv_column(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "topic": "custom_topic"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="default")
        assert cards[0]["topic_id"] == "custom_topic"

    def test_topic_falls_back_to_arg(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="fallback")
        assert cards[0]["topic_id"] == "fallback"

    def test_section_from_csv_column(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "section": "2.1"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["section_id"] == "2.1"

    def test_section_defaults_to_1(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["section_id"] == "1"

    def test_card_index_per_section(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "A1", "section": "a"},
            {"question": "Q2?", "answer": "A2", "section": "b"},
            {"question": "Q3?", "answer": "A3", "section": "a"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        a_cards = [c for c in cards if c["section_id"] == "a"]
        b_cards = [c for c in cards if c["section_id"] == "b"]
        assert [c["card_index"] for c in a_cards] == [0, 1]
        assert [c["card_index"] for c in b_cards] == [0]

    def test_tags_json_array(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "tags": '["econ", "gdp"]'},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["tags"] == '["econ", "gdp"]'

    def test_tags_comma_separated(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "tags": "econ, gdp"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        import json
        parsed = json.loads(cards[0]["tags"])
        assert parsed == ["econ", "gdp"]

    def test_missing_question_column_raises(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"answer": "A"},
        ], fieldnames=["answer"])
        with pytest.raises(ValueError, match="question"):
            parse_csv(path, deck="d", source="s", topic="t")

    def test_missing_answer_column_raises(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?"},
        ], fieldnames=["question"])
        with pytest.raises(ValueError, match="answer"):
            parse_csv(path, deck="d", source="s", topic="t")


class TestImportCsv:
    def test_import_creates_cards_in_db(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "42"},
            {"question": "Q2?", "answer": "7.5"},
        ])
        conn = init_generation_db()
        n = import_csv(conn, path, deck="test", source="src", topic="t")
        assert n == 2

    def test_import_cards_are_exact_type(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s", topic="t")
        card = conn.execute(
            "SELECT card_type FROM generation_cards"
        ).fetchone()
        assert card["card_type"] == "exact"

    def test_import_idempotent(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s", topic="t")
        n2 = import_csv(conn, path, deck="d", source="s", topic="t")
        assert n2 == 1
        total = conn.execute("SELECT COUNT(*) FROM generation_cards").fetchone()[0]
        assert total == 1

    def test_import_topic_from_filename(self, tmp_path):
        path = _write_csv(tmp_path, "gdp_data.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s")  # no topic arg
        card = conn.execute("SELECT topic_id FROM generation_cards").fetchone()
        assert card["topic_id"] == "gdp_data"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_csv_importer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement CSV importer**

Create `src/knowledge_base/srs/csv_importer.py`:

```python
"""CSV import for exact-answer cards.

Reads CSV files with question/answer columns and imports them as
exact-answer cards into the generation_cards table.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from knowledge_base.srs.generation_db import (
    init_generation_db,
    upsert_generation_card,
)


def parse_csv(
    path: Path | str,
    deck: str,
    source: str,
    topic: str | None = None,
) -> list[dict]:
    """Parse a CSV file into card dicts ready for DB insertion.

    Parameters
    ----------
    path:
        Path to the CSV file.
    deck:
        Deck name for all cards.
    source:
        Source identifier for all cards.
    topic:
        Default topic_id. Overridden by a ``topic`` column in the CSV.
        If None, defaults to the filename stem.
    """
    path = Path(path)
    if topic is None:
        topic = path.stem

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        if "question" not in fieldnames:
            raise ValueError("CSV must have a 'question' column")
        if "answer" not in fieldnames:
            raise ValueError("CSV must have an 'answer' column")

        rows = list(reader)

    # Track card_index per (topic, section) group
    section_counters: dict[tuple[str, str], int] = {}
    cards: list[dict] = []

    for row in rows:
        row_topic = row.get("topic", "").strip() or topic
        row_section = row.get("section", "").strip() or "1"

        key = (row_topic, row_section)
        idx = section_counters.get(key, 0)
        section_counters[key] = idx + 1

        # Handle tags: JSON array string or comma-separated
        raw_tags = row.get("tags", "").strip()
        if raw_tags:
            if raw_tags.startswith("["):
                tags = raw_tags  # already JSON
            else:
                tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
                tags = json.dumps(tag_list)
        else:
            tags = "[]"

        cards.append({
            "deck": deck,
            "source": source,
            "topic_id": row_topic,
            "section_id": row_section,
            "card_index": idx,
            "question": row["question"].strip(),
            "answer": row["answer"].strip(),
            "tags": tags,
            "card_type": "exact",
        })

    return cards


def import_csv(
    conn,
    path: Path | str,
    deck: str,
    source: str,
    topic: str | None = None,
) -> int:
    """Parse CSV and upsert all cards into the database. Returns card count."""
    cards = parse_csv(path, deck=deck, source=source, topic=topic)
    for card in cards:
        upsert_generation_card(conn, card)
    return len(cards)


def main() -> None:
    """CLI entry point for gen-import-csv."""
    parser = argparse.ArgumentParser(
        description="Import exact-answer cards from CSV"
    )
    parser.add_argument("file", help="Path to CSV file")
    parser.add_argument("--deck", required=True, help="Deck name")
    parser.add_argument("--source", required=True, help="Source identifier")
    parser.add_argument("--topic", default=None, help="Topic ID (default: filename stem)")
    parser.add_argument("--db", default="data/srs.db", help="Path to SRS database")
    parser.add_argument(
        "--preview", action="store_true",
        help="Print parsed card counts without writing to DB.",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}")
        return

    if args.preview:
        cards = parse_csv(path, deck=args.deck, source=args.source, topic=args.topic)
        # Group by topic/section
        groups: dict[tuple[str, str], int] = {}
        for card in cards:
            key = (card["topic_id"], card["section_id"])
            groups[key] = groups.get(key, 0) + 1
        for (topic, section), count in sorted(groups.items()):
            print(f"  {topic} > {section}  ({count} card{'s' if count != 1 else ''})")
        print(f"Total: {len(cards)} card{'s' if len(cards) != 1 else ''}")
        return

    conn = init_generation_db(db_path=args.db)
    n = import_csv(conn, path, deck=args.deck, source=args.source, topic=args.topic)
    print(f"Imported {n} card{'s' if n != 1 else ''} into {args.db}.")
```

- [ ] **Step 4: Add entry point to `pyproject.toml`**

Add to `[project.scripts]`:
```toml
gen-import-csv = "knowledge_base.srs.csv_importer:main"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_csv_importer.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/csv_importer.py tests/test_csv_importer.py pyproject.toml
git commit -m "feat: add CSV import for exact-answer cards"
```

---

### Task 4: Massed practice reshuffling algorithm

**Files:**
- Create: `tests/test_massed_practice.py`
- Modify: `src/knowledge_base/srs/generation_tui.py`

This task replaces the delay-based queue (`deque` + `delay` counter + `_pop_next`/`_decrement_delays`) with a positional-insertion list for massed practice. Ordered practice (ring buffer with `delay=0`) is unchanged.

- [ ] **Step 1: Write failing tests**

Create `tests/test_massed_practice.py`:

```python
"""Tests for the massed practice reshuffling algorithm."""

import random

import pytest

from knowledge_base.srs.generation_tui import (
    QueueItem,
    massed_requeue_position,
)


class TestMassedRequeuePosition:
    """Tests for the spacing calculation."""

    def test_fail_returns_1(self):
        assert massed_requeue_position(passed=False, pass_count=0, queue_len=10) == 1

    def test_first_pass_in_range_2_4(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=1, queue_len=20)
                     for _ in range(100)}
        assert positions <= {2, 3, 4}
        assert len(positions) > 1  # not always the same

    def test_second_pass_in_range_4_8(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=2, queue_len=20)
                     for _ in range(100)}
        assert positions <= {4, 5, 6, 7, 8}
        assert len(positions) > 1

    def test_third_pass_in_range_8_12(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=3, queue_len=20)
                     for _ in range(100)}
        assert positions <= {8, 9, 10, 11, 12}
        assert len(positions) > 1

    def test_fourth_plus_pass_in_range_8_12(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=5, queue_len=20)
                     for _ in range(100)}
        assert positions <= {8, 9, 10, 11, 12}

    def test_clamped_to_queue_length(self):
        # Queue only has 3 items — can't insert at position 8
        pos = massed_requeue_position(passed=True, pass_count=3, queue_len=3)
        assert pos == 3

    def test_masking_level_pass_uses_first_range(self):
        """Masking-level passes (pass_count=0) use 1st-pass range."""
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=0, queue_len=20)
                     for _ in range(100)}
        assert positions <= {2, 3, 4}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_massed_practice.py -v`
Expected: FAIL — `massed_requeue_position` not found

- [ ] **Step 3: Implement `massed_requeue_position`**

Add to `src/knowledge_base/srs/generation_tui.py` after the constants block (~line 101):

```python
def massed_requeue_position(passed: bool, pass_count: int, queue_len: int) -> int:
    """Calculate the position to insert a card in the massed practice queue.

    Parameters
    ----------
    passed:
        Whether the card was answered correctly.
    pass_count:
        Number of qualifying passes for this card in the session.
        For masking cards, this is type-in passes only.
        For exact cards, this is total correct answers.
        A value of 0 means masking-level pass (uses 1st-pass range).
    queue_len:
        Current number of items in the queue.
    """
    if not passed:
        return 1

    if pass_count <= 1:
        low, high = 2, 4
    elif pass_count == 2:
        low, high = 4, 8
    else:
        low, high = 8, 12

    pos = random.randint(low, high)
    return min(pos, queue_len)
```

Add `import random` to the imports at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_massed_practice.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py tests/test_massed_practice.py
git commit -m "feat: add massed practice positional reshuffling function"
```

---

### Task 5: Replace delay-based queue with positional insertion

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`

This task wires the new `massed_requeue_position` into the actual TUI queue. The `QueueItem.delay` field, `_pop_next()`, `_decrement_delays()`, and all `delay=` arguments are replaced with positional list insertion for massed practice. Ordered practice keeps its ring buffer behavior.

- [ ] **Step 1: Change queue from `deque` to `list`**

In `GenerationReviewApp.__init__` (~line 249), change:
```python
        self.queue: deque[QueueItem] = deque()
```
to:
```python
        self.queue: list[QueueItem] = []
```

Add pass counter dict:
```python
        self._pass_counts: dict[int, int] = {}  # card_id → session pass count
```

- [ ] **Step 2: Simplify `QueueItem`**

Change the `QueueItem` dataclass (~line 108):
```python
@dataclass
class QueueItem:
    """Wraps a card dict for the review queue."""
    card: dict
```

Remove the `delay: int = 0` field.

- [ ] **Step 3: Replace `_pop_next`, `_decrement_delays`, `_requeue`**

Replace `_pop_next` (~line 478):
```python
    def _pop_next(self) -> QueueItem | None:
        """Pop the next item from the front of the queue."""
        if not self.queue:
            return None
        return self.queue.pop(0)
```

Delete `_decrement_delays` entirely.

Replace `_requeue` (~line 502):
```python
    def _requeue(self, item: QueueItem, position: int | None = None) -> None:
        """Re-add an item to the queue at the given position.

        For massed practice, position is calculated by massed_requeue_position.
        For ordered practice, item goes to the end (position=None).
        """
        if position is None or position >= len(self.queue):
            self.queue.append(item)
        else:
            self.queue.insert(position, item)
        self.total_cards += 1
```

- [ ] **Step 4: Update all queue-building methods**

All methods that do `self.queue.append(QueueItem(card=..., delay=0))` — change to `self.queue.append(QueueItem(card=...))`. This affects:
- `_build_practice_queue` (~line 360)
- `_build_ordered_practice_queue` (~line 377)
- `_build_catalog_queue` (~line 413)
- `_build_paste_queue` (~line 421)
- `_build_source_filter_queue` (~line 451)
- `_build_queue` (~line 463, 476)

- [ ] **Step 5: Update `_handle_practice_pass` to use positional insertion**

Replace `_handle_practice_pass` (~line 789):

```python
    def _handle_practice_pass(
        self, item: QueueItem, card: dict, level: int
    ) -> None:
        """Handle pass in practice mode — no DB writes, no graduation."""
        card_id = card["card_id"]

        if level < MAX_MASKING_LEVEL:
            new_level = level + 1
            card["masking_level"] = new_level
            card["_practice_max_passes"] = 0
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=0, queue_len=len(self.queue),
                )
                self._requeue(item, pos)
        elif level == MAX_MASKING_LEVEL:
            passes = card.get("_practice_max_passes", 0) + 1
            card["_practice_max_passes"] = passes
            if passes >= 2:
                card["masking_level"] = PRACTICE_TYPEIN_LEVEL
                card["_practice_max_passes"] = 0
                self._finish_review()
                if self.ordered_practice:
                    self._requeue(item)
                else:
                    pos = massed_requeue_position(
                        passed=True, pass_count=0, queue_len=len(self.queue),
                    )
                    self._requeue(item, pos)
            else:
                self._finish_review()
                if self.ordered_practice:
                    self._requeue(item)
                else:
                    pos = massed_requeue_position(
                        passed=True, pass_count=0, queue_len=len(self.queue),
                    )
                    self._requeue(item, pos)
        else:
            # Type-in level pass — increment pass counter
            count = self._pass_counts.get(card_id, 0) + 1
            self._pass_counts[card_id] = count
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=count, queue_len=len(self.queue),
                )
                self._requeue(item, pos)
```

- [ ] **Step 6: Update `_handle_generation_fail` for practice mode**

In `_handle_generation_fail` (~line 820), change the practice mode block:
```python
        if self.practice_mode:
            card["masking_level"] = 0
            card["consecutive_max_passes"] = 0
            card["_practice_max_passes"] = 0
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                self._requeue(item, 1)
            return
```

- [ ] **Step 7: Update `_finish_review` and `_advance_after_grade`**

Remove `_decrement_delays()` calls from both methods:

```python
    def _advance_after_grade(self) -> None:
        self.total_reviewed += 1
        self._current_item = None
        self._show_next()

    def _finish_review(self) -> None:
        self.total_reviewed += 1
        self._awaiting_gen_grade = False
        self._awaiting_recall_grade = False
        self._current_item = None
        self._show_next()
```

- [ ] **Step 8: Update non-practice requeue calls**

In `_handle_generation_pass` (the non-practice branch, ~line 762), change:
```python
            self._requeue(item, new_level + 1)
```
to use positional insertion:
```python
            self._requeue(item, new_level + 1)
```
This already works — for global review, fixed positions are fine (not randomized).

For graduation gap (~line 787):
```python
            self._requeue(item, GRADUATION_GAP)
```
Also fine as-is.

For the `_pending_requeue` in `on_key` (~line 700), change:
```python
                    item, delay = self._pending_requeue
                    self._pending_requeue = None
                    self._requeue(item, delay)
```
This already works since `_requeue` now takes position instead of delay, and the regression rule uses position 1 (~line 986).

- [ ] **Step 9: Remove `deque` import**

Remove `from collections import deque` from imports since the queue is now a `list`.

- [ ] **Step 10: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass. The existing `test_ordered_practice.py` tests should still pass since ordered practice behavior is preserved.

- [ ] **Step 11: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "refactor: replace delay-based queue with positional insertion"
```

---

### Task 6: TUI support for exact-answer cards

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`

- [ ] **Step 1: Update `_show_generation_card` for exact cards**

In `_show_generation_card` (~line 549), add a branch at the top for exact cards. Before the existing `if self.practice_mode and level >= PRACTICE_TYPEIN_LEVEL:` block, add:

```python
        if card.get("card_type") == "exact":
            mode_label = "ordered" if self.ordered_practice else "practice"
            header = f"{location}  {progress}  ({mode_label} — exact)"
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            self.query_one("#masked-text", Static).update("")
            self.query_one("#result", Static).update("")
            self.query_one("#stats-display", Static).update("")
            self._awaiting_gen_grade = False
            self._awaiting_recall_grade = False
            self.showing_stats = False
            inp = self.query_one("#answer-input", Input)
            inp.display = True
            inp.value = ""
            inp.placeholder = "Type the answer..."
            inp.focus()
            return
```

- [ ] **Step 2: Update `on_input_submitted` for exact cards**

In `on_input_submitted` (~line 630), after getting `card` and `phase`, add a branch before the existing tokenization:

```python
        # Exact-answer cards — auto-grade
        if card.get("card_type") == "exact":
            from knowledge_base.srs.text_scoring import check_exact_answer
            correct = check_exact_answer(text, card["answer"])
            self._handle_exact_answer(correct, text)
            return
```

- [ ] **Step 3: Add `_handle_exact_answer` method**

Add to `GenerationReviewApp`:

```python
    def _handle_exact_answer(self, correct: bool, typed: str) -> None:
        """Handle an exact-answer card result — auto pass/fail."""
        item = self._current_item
        card = item.card
        card_id = card["card_id"]

        if correct:
            count = self._pass_counts.get(card_id, 0) + 1
            self._pass_counts[card_id] = count

            pass_label = f"  Pass {count}" if count > 0 else ""
            if count >= 3:
                pass_label = f"  [green]Pass {count}[/]"

            lines = [
                "[green]Correct![/]",
                "",
                f"[dim]Answer:[/] {card['answer']}",
                pass_label,
            ]
            self.query_one("#result", Static).update("\n".join(lines))
            self._hide_input()
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                pos = massed_requeue_position(
                    passed=True, pass_count=count, queue_len=len(self.queue),
                )
                self._requeue(item, pos)
        else:
            lines = [
                "[red]Incorrect[/]",
                "",
                f"[dim]Expected:[/] {card['answer']}",
                f"[dim]You typed:[/] {typed}",
            ]
            self.query_one("#result", Static).update("\n".join(lines))
            self._hide_input()
            self._finish_review()
            if self.ordered_practice:
                self._requeue(item)
            else:
                self._requeue(item, 1)
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add TUI support for exact-answer cards"
```

---

### Task 7: Per-card pass counter display for masking cards

**Files:**
- Modify: `src/knowledge_base/srs/generation_tui.py`

Task 6 already shows the pass counter for exact cards. This task adds it to masking cards at the type-in level.

- [ ] **Step 1: Update `_show_generation_feedback` to include pass counter**

In `_show_generation_feedback` (~line 657), replace with:

```python
    def _show_generation_feedback(self, diff_markup: str) -> None:
        """Show diff and prompt for pass/fail."""
        card = self._current_item.card
        card_id = card["card_id"]
        count = self._pass_counts.get(card_id, 0)

        lines = [
            diff_markup,
            "",
            "[dim]Correct:[/]",
            f"  {card['answer']}",
        ]

        # Show pass counter for type-in level (will be incremented if user passes)
        if card["masking_level"] >= PRACTICE_TYPEIN_LEVEL and count > 0:
            if count >= 3:
                lines.append(f"  [green]Pass {count}[/]")
            else:
                lines.append(f"  Pass {count}")

        lines.append("")
        lines.append("[bold]Space/Enter[/] = Pass    [bold]f[/] = Fail")
        self.query_one("#result", Static).update("\n".join(lines))
        self._awaiting_gen_grade = True
        self._hide_input()
```

- [ ] **Step 2: Update type-in pass in `_handle_practice_pass`**

The pass counter increment for masking type-in passes was already added in Task 5 Step 5. Verify it's there — in the `else` branch (type-in level):
```python
            count = self._pass_counts.get(card_id, 0) + 1
            self._pass_counts[card_id] = count
```

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add per-card pass counter display for masking type-in"
```

---

### Task 8: Update CLAUDE.md and run final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Add `gen-import-csv` to Quick Reference:
```
uv run gen-import-csv <file> --deck D --source S         # import CSV exact-answer cards
uv run gen-import-csv <file> --deck D --source S --preview  # preview without importing
uv run gen-import-csv <file> --deck D --source S --topic T  # override topic
```

Add to Architecture section under `### Generation review (`srs/`)`:
```
- `csv_importer.py` — CSV parser and `gen-import-csv` CLI for exact-answer cards
```

Add to Key Constraints under `### Generation cards (multi-source)`:
```
- **Card types**: `masking` (progressive masking, default) and `exact` (Q&A with numeric-aware matching). Card type stored in `card_type` column.
- **CSV import** (`gen-import-csv`): imports exact-answer cards from CSV with `question` and `answer` columns. Optional `topic`, `section`, `tags` columns.
- **Massed practice reshuffling**: randomized positional spacing (fail → position 1; pass → 2-4/4-8/8-12 cards back). Prevents fixed-order recall dependencies.
- **Per-card pass counter**: tracks type-in (masking) and correct answer (exact) passes per card in session. Displayed on answer screen, green at 3+.
```

Update test count from `~272` to `~300` (approximate after adding new test files).

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 3: Verify entry point**

```bash
uv run gen-import-csv --help
```

Expected: Help text with `--deck`, `--source`, `--topic`, `--preview`, `--db` options.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with exact-answer cards and CSV import"
```
