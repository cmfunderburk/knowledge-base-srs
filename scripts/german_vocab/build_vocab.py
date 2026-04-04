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
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import spacy


# Archaic spelling rules (Nietzsche-era orthography → modern)
ARCHAIC_RULES: list[tuple[re.Pattern, str]] = [
    # "Th" at word start → "T" (Thorheit→Torheit, Thiere→Tiere, Theil→Teil)
    (re.compile(r"^Th"), "T"),
    (re.compile(r"^th"), "t"),
    # "gie" → "gi" (giebt→gibt, gieng→ging)
    (re.compile(r"^gie"), "gi"),
    # "ey" → "ei" (seyn→sein)
    (re.compile(r"ey"), "ei"),
    # "eiss" / "eisst" → "eiß" / "eißt" (heisst→heißt, weiss→weiß)
    (re.compile(r"eiss(t?)$"), r"eiß\1"),
    # Terminal "ss" → "s" for words like Gleichniss→Gleichnis, diess→dies
    (re.compile(r"ss$"), "s"),
]


def normalize_archaic(word: str) -> str:
    """Normalize 19th-century German spelling to modern equivalents."""
    result = word
    for pattern, replacement in ARCHAIC_RULES:
        result = pattern.sub(replacement, result)
    return result


# spaCy POS tags for function words to exclude
FUNCTION_POS = {"ADP", "AUX", "CCONJ", "DET", "PART", "PRON", "SCONJ", "PUNCT", "SPACE", "X", "NUM", "SYM"}


def lemmatize_and_count(
    text: str, nlp: spacy.Language
) -> tuple[Counter[str], dict[str, str]]:
    """Lemmatize text with spaCy and count lemma frequencies.

    Returns:
        counts: Counter mapping lemma → frequency
        archaic_map: dict mapping lemma → archaic form (if different)
    """
    doc = nlp(text)
    counts: Counter[str] = Counter()
    archaic_map: dict[str, str] = {}

    for token in doc:
        if token.is_space or token.is_punct:
            continue
        if token.pos_ in FUNCTION_POS:
            continue
        if token.pos_ == "PROPN":
            continue
        if len(token.text) <= 2:
            continue

        lemma = token.lemma_.strip()
        if not lemma or len(lemma) <= 2:
            continue

        # Normalize archaic spellings
        modern = normalize_archaic(lemma)

        # Capitalize nouns (German convention)
        if token.pos_ == "NOUN" and not modern[0].isupper():
            modern = modern[0].upper() + modern[1:]

        # Strip spurious trailing "e" from lemmas when the original token
        # ended in "en" — spaCy sometimes returns a stem like "Tugende"
        # instead of "Tugend" for plural forms (e.g. "Tugenden" → "Tugende")
        if (
            modern.endswith("e")
            and len(modern) > 3
            and token.text.lower().endswith("en")
        ):
            modern = modern[:-1]

        # Track archaic form if normalization changed the original token
        original = token.text
        original_normalized = normalize_archaic(original)
        if original_normalized != original and modern not in archaic_map:
            archaic_map[modern] = original

        counts[modern] += 1

    return counts, archaic_map


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
