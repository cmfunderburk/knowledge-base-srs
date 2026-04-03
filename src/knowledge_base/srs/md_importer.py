"""Markdown import parser for structured study notes.

Parses two heading formats:

* **Section-keyed** — ``- 1.2: Title`` (dash + number.number: title) or
  ``## 1.2: Title`` / ``### 1.2 Title`` (hash heading + number.number)
* **LOS-keyed** — ``### LOS 1.a`` (markdown heading with "LOS" keyword)

Bullets under a section become individual cards.  Sub-bullets fold into their
parent.  Consecutive non-bullet lines join into a single card (paragraph mode).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from knowledge_base.srs.generation_db import init_generation_db, upsert_generation_card


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Section-keyed: dash heading  →  "- 1.2: Title"  or  "- 1.2 Title"
_DASH_SECTION_RE = re.compile(
    r"^-\s+(\d+\.\d+)(?::\s*|\s+)(.+)$"
)

# Section-keyed: hash heading  →  "## 1.2: Title"  or  "### 1.2 Title"
_HASH_SECTION_RE = re.compile(
    r"^#{1,6}\s+(\d+\.\d+)(?::\s*|\s+)(.+)$"
)

# LOS-keyed: "### LOS 1.a"  (any hash depth, optional extra text after id)
_LOS_SECTION_RE = re.compile(
    r"^#{1,6}\s+LOS\s+(\d+\.[a-z]+)\b",
    re.IGNORECASE,
)

# Bullet at any tab depth: optional leading tabs then "- "
_BULLET_RE = re.compile(r"^(\t*)- (.+)$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_format(lines: list[str]) -> str:
    """Return ``'section'`` or ``'los'`` based on the first recognised heading."""
    for line in lines:
        if _LOS_SECTION_RE.match(line):
            return "los"
        if _DASH_SECTION_RE.match(line) or _HASH_SECTION_RE.match(line):
            return "section"
    raise ValueError(
        "No recognised section headings found. "
        "Expected '- 1.2: Title', '## 1.2: Title', or '### LOS 1.a' patterns."
    )


def _match_section_heading(line: str) -> tuple[str, str] | None:
    """Return ``(section_id, title)`` if *line* is a section-keyed heading."""
    m = _DASH_SECTION_RE.match(line) or _HASH_SECTION_RE.match(line)
    if m:
        return m.group(1), m.group(2).strip()
    return None


def _match_los_heading(line: str) -> str | None:
    """Return ``section_id`` if *line* is a LOS-keyed heading, else ``None``."""
    m = _LOS_SECTION_RE.match(line)
    if m:
        return m.group(1)
    return None


def _parse_section_keyed(lines: list[str]) -> list[dict]:
    """Parse section-keyed format and return list of section dicts."""
    sections: list[dict] = []
    current_section: dict | None = None
    current_card_parts: list[str] = []  # parts of the in-progress card
    current_indent: int | None = None   # tab depth of current parent bullet

    def _flush_card() -> None:
        """Push the assembled card (if any) into current_section."""
        if current_section is not None and current_card_parts:
            current_section["cards"].append(" ".join(current_card_parts))
            current_card_parts.clear()

    def _flush_section() -> None:
        """Finalise current section and append to sections."""
        _flush_card()
        if current_section is not None and current_section["cards"]:
            sections.append(current_section)

    in_sections = False  # skip preamble until first heading

    for line in lines:
        # Try to match a section heading
        heading = _match_section_heading(line)
        if heading is not None:
            _flush_section()
            in_sections = True
            current_section = {
                "section_id": heading[0],
                "section_title": heading[1],
                "cards": [],
            }
            current_card_parts = []
            current_indent = None
            continue

        if not in_sections:
            continue  # still in preamble

        # Inside a section — parse bullets
        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            tabs = bullet_match.group(1)
            depth = len(tabs)
            text = bullet_match.group(2).strip()

            if current_indent is None or depth <= current_indent:
                # New top-level bullet: flush previous card, start new one
                _flush_card()
                current_indent = depth
                current_card_parts.append(text)
            else:
                # Deeper indent → sub-bullet: fold into parent card
                current_card_parts.append(text)
            continue

        # Non-bullet, non-heading line (e.g., blank or prose)
        stripped = line.strip()
        if not stripped:
            # Blank line: flush any open card
            _flush_card()
            current_indent = None
        # Otherwise ignore (shouldn't normally occur in section-keyed format)

    _flush_section()
    return sections


def _parse_los_keyed(lines: list[str]) -> list[dict]:
    """Parse LOS-keyed format and return list of section dicts."""
    sections: list[dict] = []
    current_section: dict | None = None
    current_paragraph: list[str] = []  # lines in current paragraph

    def _flush_paragraph() -> None:
        """Push assembled paragraph (if any) as a card."""
        if current_section is not None and current_paragraph:
            current_section["cards"].append(" ".join(current_paragraph))
            current_paragraph.clear()

    def _flush_section() -> None:
        _flush_paragraph()
        if current_section is not None and current_section["cards"]:
            sections.append(current_section)

    for line in lines:
        los_id = _match_los_heading(line)
        if los_id is not None:
            _flush_section()
            current_section = {
                "section_id": los_id,
                "section_title": None,
                "cards": [],
            }
            current_paragraph = []
            continue

        if current_section is None:
            continue  # preamble before first LOS

        stripped = line.strip()

        if not stripped:
            # Blank line ends the current paragraph
            _flush_paragraph()
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            # Each bullet is its own card; flush paragraph first
            _flush_paragraph()
            text = bullet_match.group(2).strip()
            current_section["cards"].append(text)
            continue

        # Plain prose line — accumulate into current paragraph
        current_paragraph.append(stripped)

    _flush_section()
    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_markdown(
    text: str,
    format: str | None = None,
) -> list[dict]:
    """Parse structured markdown into sections with cards.

    Parameters
    ----------
    text:
        Raw markdown content.
    format:
        Force ``'section'`` or ``'los'`` parsing.  If ``None``, auto-detect
        from the first recognised heading found in *text*.

    Returns
    -------
    list[dict]
        Each dict has keys ``section_id`` (str), ``section_title`` (str | None),
        and ``cards`` (list[str]).  Empty sections are omitted.

    Raises
    ------
    ValueError
        If no recognised headings are found (regardless of *format*).
    """
    lines = text.splitlines()

    if format is None:
        fmt = _detect_format(lines)
    else:
        # Even with a forced format, validate that headings exist.
        fmt = _detect_format(lines)
        # Honour the caller's explicit format choice (may differ from detected).
        fmt = format

    if fmt == "section":
        return _parse_section_keyed(lines)
    elif fmt == "los":
        return _parse_los_keyed(lines)
    else:
        raise ValueError(f"Unknown format {fmt!r}. Expected 'section' or 'los'.")


def import_markdown(
    conn: sqlite3.Connection,
    text: str,
    deck: str,
    topic_id: str,
    source: str,
    format: str | None = None,
) -> int:
    """Parse *text* and upsert each card into the generation_cards table.

    Parameters
    ----------
    conn:
        Open SQLite connection (generation tables must already exist).
    text:
        Raw markdown content to parse.
    deck:
        Deck name for all imported cards.
    topic_id:
        Topic/reading identifier for all imported cards.
    source:
        Source identifier (e.g. ``'markdown'``) for all imported cards.
    format:
        Force ``'section'`` or ``'los'`` parsing. If ``None``, auto-detect.

    Returns
    -------
    int
        Number of cards upserted.
    """
    sections = parse_markdown(text, format=format)
    tags = json.dumps([f"reading::{topic_id}", f"source::{source}"])

    count = 0
    for section in sections:
        section_id: str = section["section_id"]
        section_title: str | None = section["section_title"]
        cards: list[str] = section["cards"]
        total = len(cards)

        for card_index, answer in enumerate(cards):
            if section_title:
                question = (
                    f"{section_id}: {section_title} [{card_index + 1}/{total}]"
                )
            else:
                question = f"LOS {section_id} [{card_index + 1}/{total}]"

            card = {
                "deck": deck,
                "source": source,
                "topic_id": topic_id,
                "section_id": section_id,
                "section_title": section_title,
                "card_index": card_index,
                "question": question,
                "answer": answer,
                "tags": tags,
            }
            upsert_generation_card(conn, card)
            count += 1

    return count


def main() -> None:
    """CLI entry point for importing markdown study notes into the SRS database."""
    parser = argparse.ArgumentParser(
        description="Import structured markdown notes into the generation cards DB."
    )
    parser.add_argument("file", help="Path to the markdown file to import.")
    parser.add_argument("--deck", required=True, help="Deck name.")
    parser.add_argument("--topic", required=True, help="Topic/reading number.")
    parser.add_argument("--source", required=True, help="Source identifier.")
    parser.add_argument(
        "--format",
        choices=["section", "los"],
        default=None,
        help="Force a specific parsing format (auto-detect if omitted).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Print parsed sections and card counts without writing to DB.",
    )
    parser.add_argument(
        "--db",
        default="data/srs.db",
        help="Path to the SQLite database (default: data/srs.db).",
    )
    args = parser.parse_args()

    text = Path(args.file).read_text(encoding="utf-8")

    if args.preview:
        sections = parse_markdown(text, format=args.format)
        total = 0
        for section in sections:
            count = len(section["cards"])
            total += count
            title_part = (
                f": {section['section_title']}" if section["section_title"] else ""
            )
            print(f"  {section['section_id']}{title_part}  ({count} card{'s' if count != 1 else ''})")
        print(f"Total: {total} card{'s' if total != 1 else ''}")
        return

    conn = init_generation_db(db_path=args.db)
    n = import_markdown(
        conn=conn,
        text=text,
        deck=args.deck,
        topic_id=args.topic,
        source=args.source,
        format=args.format,
    )
    print(f"Imported {n} card{'s' if n != 1 else ''} into {args.db}.")
