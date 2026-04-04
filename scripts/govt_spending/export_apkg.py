"""Export cards.csv to an Anki .apkg package.

Reads: data/govt_spending/cards.csv
Writes: data/govt_spending/govt_spending.apkg

Uses the Enhanced Cloze Type-In 1.0 note type (model ID 1775162181082).
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import genanki

# Must match the installed Enhanced Cloze Type-In 1.0 note type
MODEL_ID = 1775162181082

# Stable deck IDs (random large integers, consistent across re-exports)
DECK_BY_NATION_ID = 2010040401
DECK_BY_CATEGORY_ID = 2010040402

DATA_DIR = Path("data/govt_spending")

# genanki model mirroring Enhanced Cloze Type-In 1.0 fields.
# Templates are placeholders — on import, Anki will use the templates
# from the existing note type if the model name matches.
model = genanki.Model(
    MODEL_ID,
    "Enhanced Cloze Type-In 1.0",
    fields=[
        {"name": "Content"},
        {"name": "Note"},
        {"name": "Mnemonics"},
        {"name": "Extra"},
        {"name": "Cloze99"},
    ],
    templates=[
        {
            "name": "Enhanced Cloze Type-In",
            "qfmt": "{{cloze:Content}}",
            "afmt": "{{cloze:Content}}<br>{{Note}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)


def stable_guid(card_id: str) -> str:
    """Generate a stable GUID from card_id for safe re-import."""
    h = hashlib.sha256(card_id.encode()).hexdigest()
    # genanki expects a string; use first 10 hex chars
    return h[:10]


def export_apkg() -> Path:
    """Read cards.csv and export .apkg."""
    deck_by_nation = genanki.Deck(DECK_BY_NATION_ID, "Government Spending::By Nation")
    deck_by_category = genanki.Deck(DECK_BY_CATEGORY_ID, "Government Spending::By Category")

    cards_path = DATA_DIR / "cards.csv"
    count = 0

    with open(cards_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            note = genanki.Note(
                model=model,
                fields=[
                    row["content"],   # Content
                    row["note"],      # Note (SVG chart)
                    "",               # Mnemonics
                    "",               # Extra
                    "",               # Cloze99
                ],
                tags=row["tags"].split(),
                guid=stable_guid(row["card_id"]),
            )

            if row["deck"] == "by_nation":
                deck_by_nation.add_note(note)
            else:
                deck_by_category.add_note(note)

            count += 1

    out_path = DATA_DIR / "govt_spending.apkg"
    genanki.Package([deck_by_nation, deck_by_category]).write_to_file(str(out_path))
    print(f"Wrote {out_path}: {count} cards")
    return out_path


if __name__ == "__main__":
    export_apkg()
