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

    section_counters: dict[tuple[str, str], int] = {}
    cards: list[dict] = []

    for row in rows:
        row_topic = row.get("topic", "").strip() or topic
        row_section = row.get("section", "").strip() or "1"

        key = (row_topic, row_section)
        idx = section_counters.get(key, 0)
        section_counters[key] = idx + 1

        raw_tags = row.get("tags", "").strip()
        if raw_tags:
            if raw_tags.startswith("["):
                tags = raw_tags
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
        groups: dict[tuple[str, str], int] = {}
        for card in cards:
            key = (card["topic_id"], card["section_id"])
            groups[key] = groups.get(key, 0) + 1
        for (topic_id, section), count in sorted(groups.items()):
            print(f"  {topic_id} > {section}  ({count} card{'s' if count != 1 else ''})")
        print(f"Total: {len(cards)} card{'s' if len(cards) != 1 else ''}")
        return

    conn = init_generation_db(db_path=args.db)
    n = import_csv(conn, path, deck=args.deck, source=args.source, topic=args.topic)
    print(f"Imported {n} card{'s' if n != 1 else ''} into {args.db}.")
