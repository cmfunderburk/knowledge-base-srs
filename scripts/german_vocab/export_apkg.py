"""Export reviewed cards.csv to a bidirectional Anki .apkg package.

Reads: data/german_vocab/cards.csv
Writes: data/german_vocab/german_vocab_philosophy.apkg

Creates a custom note type with DE->EN and EN->DE templates.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import genanki

MODEL_ID = 2026040481
DECK_ID = 2026040482

DATA_DIR = Path("data/german_vocab")

# Single deck; Anki generates one card per template per note.
# After import, use Anki's per-template "Deck Override" to split
# DE->EN and EN->DE cards into subdecks if desired.

model = genanki.Model(
    MODEL_ID,
    "German Vocab Philosophy",
    fields=[
        {"name": "German"},
        {"name": "English"},
        {"name": "POS"},
        {"name": "Example_DE"},
        {"name": "Example_EN"},
        {"name": "Archaic_Form"},
        {"name": "Source"},
        {"name": "Frequency"},
    ],
    templates=[
        {
            "name": "DE -> EN",
            "qfmt": (
                '<div class="german">{{German}}</div>'
                '{{#Archaic_Form}}<div class="archaic">({{Archaic_Form}})</div>{{/Archaic_Form}}'
                '<div class="pos">{{POS}}</div>'
            ),
            "afmt": (
                '{{FrontSide}}<hr id="answer">'
                '<div class="english">{{English}}</div>'
                '{{#Example_DE}}<div class="example">'
                "<p>{{Example_DE}}</p>"
                "<p><em>{{Example_EN}}</em></p>"
                "</div>{{/Example_DE}}"
            ),
        },
        {
            "name": "EN -> DE",
            "qfmt": (
                '<div class="english">{{English}}</div>'
                '<div class="pos">{{POS}}</div>'
            ),
            "afmt": (
                '{{FrontSide}}<hr id="answer">'
                '<div class="german">{{German}}</div>'
                '{{#Archaic_Form}}<div class="archaic">({{Archaic_Form}})</div>{{/Archaic_Form}}'
                '{{#Example_DE}}<div class="example">'
                "<p>{{Example_DE}}</p>"
                "<p><em>{{Example_EN}}</em></p>"
                "</div>{{/Example_DE}}"
            ),
        },
    ],
    css=(
        ".card { font-family: Georgia, serif; font-size: 20px; text-align: center; }\n"
        ".german { font-size: 28px; font-weight: bold; margin-bottom: 8px; }\n"
        ".english { font-size: 24px; margin-bottom: 8px; }\n"
        ".pos { font-size: 14px; color: #888; font-style: italic; }\n"
        ".archaic { font-size: 14px; color: #999; margin-bottom: 4px; }\n"
        ".example { font-size: 16px; color: #555; margin-top: 12px; }\n"
    ),
)


def stable_guid(word: str) -> str:
    """Generate a stable GUID from the German word for safe re-import."""
    h = hashlib.sha256(word.encode()).hexdigest()
    return h[:10]


def export_apkg(csv_path: Path, out_path: Path) -> int:
    """Read cards.csv and export bidirectional .apkg.

    Returns the number of notes exported.
    """
    deck = genanki.Deck(DECK_ID, "German Vocabulary::Philosophy")

    count = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("needs_review", "").strip():
                continue
            if not row.get("english", "").strip():
                continue

            note = genanki.Note(
                model=model,
                fields=[
                    row["german"],
                    row["english"],
                    row.get("pos", ""),
                    row.get("example_de", ""),
                    row.get("example_en", ""),
                    row.get("archaic_form", ""),
                    row.get("source", ""),
                    row.get("frequency", ""),
                ],
                guid=stable_guid(row["german"]),
            )
            deck.add_note(note)
            count += 1

    genanki.Package([deck]).write_to_file(str(out_path))
    return count


def main():
    csv_path = DATA_DIR / "cards.csv"
    out_path = DATA_DIR / "german_vocab_philosophy.apkg"

    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run build_vocab.py first.")
        return

    count = export_apkg(csv_path, out_path)
    print(f"Wrote {out_path}: {count} notes ({count * 2} cards)")
    print("Tip: In Anki, use Browse → Cards → Deck Override to split")
    print("DE→EN and EN→DE cards into separate subdecks.")


if __name__ == "__main__":
    main()
