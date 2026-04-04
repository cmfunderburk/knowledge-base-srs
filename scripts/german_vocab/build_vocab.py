"""Build German vocabulary CSV from philosophical texts.

Tokenizes Nietzsche and Wittgenstein texts, lemmatizes with spaCy,
filters against an existing frequency deck, fetches Wiktionary
definitions, and writes a review CSV.

Usage:
    python -m scripts.german_vocab.build_vocab [--force]
"""

from __future__ import annotations

import re
import sqlite3
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import spacy


def load_exclusion_set(apkg_path: Path) -> set[str]:
    """Extract all German word forms from an .apkg into a lowercase set.

    Parses field index 1 from each note (the German word field), expands
    comma-separated forms, strips article prefixes and declension suffixes.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extractall(tmp_path)

        # Try anki21 first, fall back to anki2
        db_path = tmp_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmp_path / "collection.anki2"

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT flds FROM notes").fetchall()
        conn.close()

    articles = ("der ", "die ", "das ", "den ", "dem ", "des ")
    forms: set[str] = set()

    for (flds,) in rows:
        fields = flds.split("\x1f")
        if len(fields) < 2:
            continue
        german_entry = fields[1].strip().lower()
        for form in german_entry.split(","):
            form = form.strip()
            # Strip article prefixes
            for art in articles:
                if form.startswith(art):
                    form = form[len(art):]
                    break
            # Strip declension suffixes like -en, -e
            form = re.sub(r"\s*-[^ ]*$", "", form).strip()
            if form:
                forms.add(form)
                # Also add individual words from multi-word forms
                for word in form.split():
                    if len(word) > 1:
                        forms.add(word)

    return forms


def load_zarathustra(path: Path) -> str:
    """Load Zarathustra text, stripping Project Gutenberg boilerplate."""
    text = path.read_text(encoding="utf-8")
    start = text.find("*** START OF")
    if start != -1:
        text = text[text.index("\n", start) + 1:]
    end = text.find("*** END OF")
    if end != -1:
        text = text[:end]
    return text.strip()


def load_wittgenstein(path: Path) -> str:
    """Load Wittgenstein text, stripping YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
    return text.strip()


def filter_non_german(text: str, nlp: spacy.Language) -> str:
    """Remove non-German passages (Latin quotes etc.) using spaCy POS tagging.

    Processes text sentence-by-sentence. Drops any sentence where more than
    50% of tokens are tagged as X (foreign) or PUNCT.
    """
    doc = nlp(text)
    german_sents = []
    for sent in doc.sents:
        tokens = [t for t in sent if not t.is_space]
        if not tokens:
            continue
        foreign_count = sum(1 for t in tokens if t.pos_ in ("X", "PUNCT"))
        if foreign_count / len(tokens) < 0.5:
            german_sents.append(sent.text)
    return " ".join(german_sents)
