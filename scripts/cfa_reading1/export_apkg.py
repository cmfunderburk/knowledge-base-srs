"""Export CFA Reading 1 flashcards to an Anki .apkg package.

Writes: scripts/cfa_reading1/cfa_reading1.apkg

Two note types:
- Enhanced Cloze 2.1 v2 (cloze deletion, matches installed addon)
- Basic (standard Q&A)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

# --- Stable IDs (must not collide with other export scripts) -----------

CLOZE_MODEL_ID = 2026040701
BASIC_MODEL_ID = 2026040702
DECK_ID = 2026040703

OUT_DIR = Path(__file__).parent

# --- Models ------------------------------------------------------------

cloze_model = genanki.Model(
    CLOZE_MODEL_ID,
    "Enhanced Cloze 2.1 v2",
    fields=[
        {"name": "Content"},
        {"name": "Note"},
        {"name": "Mnemonics"},
        {"name": "Extra"},
        {"name": "Cloze99"},
    ],
    templates=[
        {
            "name": "Enhanced Cloze",
            "qfmt": "{{cloze:Content}}",
            "afmt": "{{cloze:Content}}<br>{{Note}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)

basic_model = genanki.Model(
    BASIC_MODEL_ID,
    "Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        },
    ],
)


def stable_guid(card_id: str) -> str:
    """Generate a stable GUID from card_id for safe re-import."""
    h = hashlib.sha256(card_id.encode()).hexdigest()
    return h[:10]
