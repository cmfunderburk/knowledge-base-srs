"""Import pipeline for CFA LOS generation cards.

Reads LOS statements from a JSON file and upserts them into the
generation_cards table. Designed to be idempotent — re-importing
preserves all scheduling and phase state.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from knowledge_base.srs.generation_db import init_generation_db, upsert_generation_card

DEFAULT_DATA_PATH = Path("data/cfa_level1_los.json")
DEFAULT_DB_PATH = Path("data/srs.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert a title to a tag-friendly slug.

    Lowercases, replaces spaces with underscores, and strips colons and commas.
    """
    text = text.lower()
    text = re.sub(r"[:,]", "", text)
    text = text.replace(" ", "_")
    return text


# ---------------------------------------------------------------------------
# Core import
# ---------------------------------------------------------------------------


def import_los(
    conn: sqlite3.Connection,
    data_path: str | Path | None = None,
) -> int:
    """Read JSON LOS data and upsert into generation_cards.

    Parameters
    ----------
    conn:
        An open SQLite connection with the generation schema initialised.
    data_path:
        Path to the JSON file. Defaults to ``data/cfa_level1_los.json``.

    Returns
    -------
    int
        Number of cards upserted.
    """
    resolved_path = Path(data_path) if data_path is not None else DEFAULT_DATA_PATH

    with open(resolved_path) as f:
        data = json.load(f)

    deck = data["deck"]
    count = 0

    for reading in data["readings"]:
        number = reading["number"]
        title = reading["title"]
        book = reading["book"]
        topic_slug = _slugify(title)

        tags = json.dumps([
            f"reading::{number}",
            f"topic::{topic_slug}",
            f"book::{book}",
        ])

        for los in reading["los"]:
            section_id = los["id"]
            question = f"What is LOS {section_id}? ({title})"
            answer = los["text"]

            upsert_generation_card(conn, {
                "deck": deck,
                "source": "los",
                "topic_id": str(number),
                "section_id": section_id,
                "card_index": 0,
                "question": question,
                "answer": answer,
                "tags": tags,
            })
            count += 1

    return count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: import LOS data into the generation_cards table."""
    parser = argparse.ArgumentParser(
        description="Import CFA LOS statements into the generation_cards table"
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--data",
        default=None,
        help=f"Path to LOS JSON file (default: {DEFAULT_DATA_PATH})",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_generation_db(db_path=str(db_path))

    data_path = Path(args.data) if args.data else DEFAULT_DATA_PATH
    count = import_los(conn, data_path=data_path)
    print(f"Imported {count} LOS cards into {db_path}")
