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
import re
import sqlite3
from pathlib import Path


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
