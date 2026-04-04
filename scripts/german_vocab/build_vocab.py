"""Build German vocabulary CSV from philosophical texts.

Tokenizes Nietzsche and Wittgenstein texts, lemmatizes with spaCy,
filters against an existing frequency deck, fetches Wiktionary
definitions, and writes a review CSV.

Usage:
    python -m scripts.german_vocab.build_vocab [--force]
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
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


WIKTIONARY_API = "https://en.wiktionary.org/api/rest_v1/page/definition"
USER_AGENT = "GermanVocabDeckBuilder/1.0 (educational project)"
FETCH_DELAY = 0.2  # seconds between requests


def load_cached(cache_dir: Path, word: str) -> dict | None:
    """Load a cached Wiktionary response, or None on miss."""
    cache_file = cache_dir / f"{urllib.parse.quote(word, safe='')}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return None


def save_cached(cache_dir: Path, word: str, data: dict) -> None:
    """Save a Wiktionary response to the cache."""
    cache_file = cache_dir / f"{urllib.parse.quote(word, safe='')}.json"
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fetch_wiktionary(word: str) -> dict | None:
    """Fetch a word definition from the Wiktionary REST API."""
    url = f"{WIKTIONARY_API}/{urllib.parse.quote(word)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError:
        return None
    except (urllib.error.URLError, TimeoutError):
        return None


def parse_wiktionary_response(data: dict) -> dict | None:
    """Parse a Wiktionary response into card fields.

    Returns dict with keys: pos, english, example_de, example_en.
    Returns None if no German entry found.
    """
    if "de" not in data:
        return None

    entries = data["de"]
    if not entries:
        return None

    entry = entries[0]
    pos = entry.get("partOfSpeech", "")
    definitions = entry.get("definitions", [])

    english_parts = []
    example_de = ""
    example_en = ""
    for defn in definitions[:2]:
        raw = defn.get("definition", "")
        clean = re.sub(r"<[^>]+>", "", raw).strip()
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            english_parts.append(clean)

        if not example_de:
            examples = defn.get("parsedExamples", [])
            if examples:
                ex = examples[0]
                example_de = re.sub(r"<[^>]+>", "", ex.get("example", "")).strip()
                example_en = re.sub(r"<[^>]+>", "", ex.get("translation", "")).strip()

    if not english_parts:
        return None

    return {
        "pos": pos,
        "english": ", ".join(english_parts),
        "example_de": example_de,
        "example_en": example_en,
    }


def fetch_definition(word: str, cache_dir: Path, pos_hint: str = "") -> dict | None:
    """Fetch and parse a Wiktionary definition, with caching and fallback."""
    cached = load_cached(cache_dir, word)
    if cached is not None:
        result = parse_wiktionary_response(cached)
        if result is not None:
            return result

    data = fetch_wiktionary(word)
    time.sleep(FETCH_DELAY)

    if data is not None:
        save_cached(cache_dir, word, data)
        result = parse_wiktionary_response(data)
        if result is not None:
            return result

    # Fallback: try opposite case
    alt = word[0].lower() + word[1:] if word[0].isupper() else word[0].upper() + word[1:]
    if alt != word:
        data = fetch_wiktionary(alt)
        time.sleep(FETCH_DELAY)
        if data is not None:
            save_cached(cache_dir, alt, data)
            result = parse_wiktionary_response(data)
            if result is not None:
                return result

    save_cached(cache_dir, word, {})
    return None


CSV_COLUMNS = [
    "german", "english", "pos", "example_de", "example_en",
    "archaic_form", "source", "frequency", "needs_review",
]


def write_csv(
    cards: list[dict], path: Path, *, force: bool = False
) -> None:
    """Write card data to CSV.

    Raises FileExistsError if path exists and force is False.
    """
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists. Use --force to overwrite."
        )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for card in cards:
            writer.writerow(card)
