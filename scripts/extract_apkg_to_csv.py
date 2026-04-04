"""Extract Anki .apkg decks into CSVs for gen-import-csv.

One-time script to convert existing knowledge_base and indicator_guide
.apkg files into the CSV format expected by gen-import-csv.

Usage:
    python scripts/extract_apkg_to_csv.py

Outputs CSVs to data/csv_import/ organized by source deck.
"""

import csv
import re
import shutil
import sqlite3
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent

# .apkg files and their target source names
KNOWLEDGE_BASE_DECKS = {
    "knowledge_base.apkg": "development",
    "knowledge_base_tech_adoption.apkg": "tech_adoption",
    "knowledge_base_conflict_security.apkg": "conflict_security",
    "knowledge_base_finance.apkg": "finance",
    "knowledge_base_urban_areas.apkg": "urban_areas",
}

INDICATOR_GUIDE = "indicator_guide.apkg"
DESCRIPTIVE_STATS = "knowledge_base_descriptive_stats.apkg"

OUTPUT_DIR = ROOT / "data" / "csv_import"

FIELD_SEP = "\x1f"


def extract_anki_db(apkg_path: Path, tmp_dir: Path) -> sqlite3.Connection:
    """Extract .apkg (zip) and return connection to collection.anki2."""
    with zipfile.ZipFile(apkg_path, "r") as zf:
        zf.extractall(tmp_dir)
    db_path = tmp_dir / "collection.anki2"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def extract_knowledge_base_deck(apkg_path: Path, source: str, out_dir: Path) -> int:
    """Extract a knowledge_base deck into a CSV.

    Fields in these decks: question \x1f answer \x1f notes \x1f confidence_level
    Tags contain: category::X indicator::Y entity::Z entity_type::T era::E
    """
    with TemporaryDirectory() as tmp:
        conn = extract_anki_db(apkg_path, Path(tmp))
        rows = conn.execute("SELECT flds, tags FROM notes").fetchall()
        conn.close()

    cards = []
    for row in rows:
        fields = row["flds"].split(FIELD_SEP)
        question = fields[0].strip()
        answer = fields[1].strip() if len(fields) > 1 else ""

        # Parse tags for topic/section metadata
        tags = row["tags"].strip().split() if row["tags"] else []
        indicator = ""
        entity = ""
        era = ""
        for tag in tags:
            if tag.startswith("indicator::"):
                indicator = tag.split("::")[1]
            elif tag.startswith("entity::"):
                entity = tag.split("::")[1]
            elif tag.startswith("era::"):
                era = tag.split("::")[1]

        cards.append({
            "question": question,
            "answer": answer,
            "topic": indicator or source,
            "section": era or "current",
            "tags": ", ".join(tags),
        })

    out_path = out_dir / f"{source}.csv"
    _write_csv(out_path, cards)
    return len(cards)


def extract_indicator_guide(apkg_path: Path, out_dir: Path) -> int:
    """Extract numerical cloze cards from the indicator guide.

    Cloze format: "GDP per capita (PPP) for rich countries: {{c1::~$50,000–80,000}}"
    Transforms to: question="GDP per capita (PPP) for rich countries:" answer="~$50,000–80,000"

    Filters: only cards containing {{c1::...}} with a numeric-looking answer
    (starts with ~, <, >, or a digit, or $).
    """
    cloze_re = re.compile(r"\{\{c1::(.+?)\}\}")
    # Match answers that look numerical: start with digit, ~, <, >, $, or negative
    numerical_re = re.compile(r"^[~<>$\d\-]")

    with TemporaryDirectory() as tmp:
        conn = extract_anki_db(apkg_path, Path(tmp))
        rows = conn.execute("SELECT flds, tags FROM notes").fetchall()
        conn.close()

    cards = []
    for row in rows:
        fields = row["flds"].split(FIELD_SEP)
        text = fields[0].strip()

        match = cloze_re.search(text)
        if not match:
            continue

        answer = match.group(1).strip()
        if not numerical_re.match(answer):
            continue

        # Build question by removing the cloze markup
        question = cloze_re.sub("___", text).strip()

        # Parse tags
        tags = row["tags"].strip().split() if row["tags"] else []
        section = ""
        indicator = ""
        for tag in tags:
            if tag.startswith("section::"):
                section = tag.split("::")[1]
            elif tag.startswith("indicator::"):
                indicator = tag.split("::")[1]

        # Use extra field as hint if present
        hint = fields[1].strip() if len(fields) > 1 and fields[1].strip() else ""
        if hint:
            question = f"{question} ({hint})"

        cards.append({
            "question": question,
            "answer": answer,
            "topic": indicator or section or "general",
            "section": section or "general",
            "tags": ", ".join(tags),
        })

    out_path = out_dir / "indicator_guide.csv"
    _write_csv(out_path, cards)
    return len(cards)


def extract_descriptive_stats(apkg_path: Path, out_dir: Path) -> int:
    """Extract descriptive stats cards.

    These are multi-cloze cards like:
    "Across all 170 countries, Armed forces as of 2020:<br>Mean: {{c1::160}}<br>..."

    Each card has multiple cloze deletions. We split each stat into its own card.
    """
    cloze_re = re.compile(r"\{\{c1::(.+?)\}\}")

    with TemporaryDirectory() as tmp:
        conn = extract_anki_db(apkg_path, Path(tmp))
        rows = conn.execute("SELECT flds, tags FROM notes").fetchall()
        conn.close()

    cards = []
    for row in rows:
        fields = row["flds"].split(FIELD_SEP)
        text = fields[0].strip()

        # Parse the header: "Across all N countries, INDICATOR as of YEAR:"
        # Then each line is "Stat: {{c1::value}}"
        lines = text.replace("<br>", "\n").split("\n")
        header = lines[0].strip() if lines else ""

        # Clean header of any cloze markers
        header_clean = cloze_re.sub("___", header)

        tags = row["tags"].strip().split() if row["tags"] else []

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            match = cloze_re.search(line)
            if not match:
                continue

            answer = match.group(1).strip()
            # Build question: "Across all N countries, INDICATOR: Mean?"
            stat_label = cloze_re.sub("___", line).split(":")[0].strip()
            question = f"{header_clean} {stat_label}?"

            cards.append({
                "question": question,
                "answer": answer,
                "topic": "descriptive_stats",
                "section": stat_label.lower().replace(" ", "_"),
                "tags": ", ".join(tags),
            })

    out_path = out_dir / "descriptive_stats.csv"
    _write_csv(out_path, cards)
    return len(cards)


def _write_csv(path: Path, cards: list[dict]) -> None:
    """Write cards to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["question", "answer", "topic", "section", "tags"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cards)
    print(f"  Wrote {len(cards)} cards to {path}")


def main():
    print("Extracting knowledge_base decks...")
    total = 0
    for apkg_name, source in KNOWLEDGE_BASE_DECKS.items():
        apkg_path = ROOT / apkg_name
        if not apkg_path.exists():
            print(f"  SKIP: {apkg_name} not found")
            continue
        n = extract_knowledge_base_deck(apkg_path, source, OUTPUT_DIR)
        total += n

    # Indicator guide
    ig_path = ROOT / INDICATOR_GUIDE
    if ig_path.exists():
        print("\nExtracting indicator_guide (numerical cloze only)...")
        n = extract_indicator_guide(ig_path, OUTPUT_DIR)
        total += n
    else:
        print(f"\n  SKIP: {INDICATOR_GUIDE} not found")

    # Descriptive stats
    ds_path = ROOT / DESCRIPTIVE_STATS
    if ds_path.exists():
        print("\nExtracting descriptive_stats...")
        n = extract_descriptive_stats(ds_path, OUTPUT_DIR)
        total += n
    else:
        print(f"\n  SKIP: {DESCRIPTIVE_STATS} not found")

    print(f"\nTotal: {total} cards extracted to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
