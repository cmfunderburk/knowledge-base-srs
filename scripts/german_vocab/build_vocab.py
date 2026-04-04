"""Build German vocabulary CSV from philosophical texts.

Tokenizes Nietzsche and Wittgenstein texts, lemmatizes with spaCy,
filters against an existing frequency deck, fetches Wiktionary
definitions, and writes a review CSV.

Usage:
    python -m scripts.german_vocab.build_vocab [--force]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import spacy

# Paths
TEXTS_DIR = Path("resources/texts")
ZARATHUSTRA_PATH = TEXTS_DIR / "Also Sprach Zarathustra.txt"
WITTGENSTEIN_PATH = TEXTS_DIR / "Philosophische Untersuchungen.md"
FREQ_DECK_PATH = Path.home() / "Dropbox" / "autodidact 2025" / "GREATS" / "English-German_Sorted_by_Frequency.apkg"
DATA_DIR = Path("data/german_vocab")
CACHE_DIR = DATA_DIR / ".wiktionary_cache"
CSV_PATH = DATA_DIR / "cards.csv"

MIN_FREQUENCY = 4


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

    Processes in paragraph-sized chunks via nlp.pipe() for speed.

    Returns:
        counts: Counter mapping lemma → frequency
        archaic_map: dict mapping lemma → archaic form (if different)
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    counts: Counter[str] = Counter()
    archaic_map: dict[str, str] = {}

    for doc in nlp.pipe(paragraphs, batch_size=50):
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

    Processes text in paragraph-sized chunks via nlp.pipe() for speed.
    Drops any sentence where more than 50% of tokens are tagged as X
    (foreign) or PUNCT.
    """
    # Split into paragraphs to avoid processing one huge document
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    german_sents = []
    for doc in nlp.pipe(paragraphs, batch_size=50):
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
FETCH_DELAY = 0.5  # seconds between requests (conservative to avoid 429s)


def _cache_path(cache_dir: Path, word: str) -> Path:
    """Generate a case-safe cache filename using SHA-256 hash.

    Avoids Dropbox case-conflict issues on case-insensitive filesystems.
    """
    h = hashlib.sha256(word.encode()).hexdigest()[:16]
    return cache_dir / f"{h}.json"


def load_cached(cache_dir: Path, word: str) -> dict | None:
    """Load a cached Wiktionary response, or None on miss."""
    cache_file = _cache_path(cache_dir, word)
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return None


def save_cached(cache_dir: Path, word: str, data: dict) -> None:
    """Save a Wiktionary response to the cache."""
    cache_file = _cache_path(cache_dir, word)
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fetch_wiktionary(word: str) -> dict | None:
    """Fetch a word definition from the Wiktionary REST API.

    Retries on 429 (rate limit) with exponential backoff.
    Returns None on 404 or persistent errors.
    """
    url = f"{WIKTIONARY_API}/{urllib.parse.quote(word)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt  # 1, 2, 4, 8 seconds
                print(f"  Rate limited on '{word}', waiting {wait}s...")
                time.sleep(wait)
                continue
            if e.code == 404:
                return None
            return None
        except (urllib.error.URLError, TimeoutError):
            return None
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


def _try_cached(word: str, cache_dir: Path) -> dict | None:
    """Check cache only — no network request."""
    cached = load_cached(cache_dir, word)
    if cached is not None:
        return parse_wiktionary_response(cached)
    return None


def _try_fetch(word: str, cache_dir: Path) -> dict | None:
    """Try fetching a single word from Wiktionary, using cache first."""
    cached = load_cached(cache_dir, word)
    if cached is not None:
        return parse_wiktionary_response(cached)

    data = fetch_wiktionary(word)
    time.sleep(FETCH_DELAY)
    if data is not None:
        save_cached(cache_dir, word, data)
        return parse_wiktionary_response(data)
    return None


def fetch_definition(word: str, cache_dir: Path, pos_hint: str = "") -> dict | None:
    """Fetch and parse a Wiktionary definition, with caching and fallback.

    Strategy (minimizes API calls to avoid rate limiting):
    1. Check cache for word and all fallback forms (free)
    2. Fetch word as-is from API
    3. Fetch case-flipped variant
    4. Fetch with -e appended (spaCy truncation fix)
    5. Give up
    """
    # Generate all forms to try
    forms = [word]
    # Opposite case
    alt = word[0].lower() + word[1:] if word[0].isupper() else word[0].upper() + word[1:]
    if alt != word:
        forms.append(alt)
    # +e variants (truncated nouns: Gedank→Gedanke, Seel→Seele)
    forms.append(word + "e")
    if alt != word:
        forms.append(alt + "e")
    # +en (truncated verbs)
    forms.append(word + "en")
    # Archaic normalization
    archaic = normalize_archaic(word)
    if archaic != word:
        forms.append(archaic)
        forms.append(archaic + "e")

    # Deduplicate
    seen = set()
    unique_forms = []
    for f in forms:
        if f not in seen:
            seen.add(f)
            unique_forms.append(f)

    # Phase 1: check cache for ALL forms (no network cost)
    for form in unique_forms:
        result = _try_cached(form, cache_dir)
        if result is not None:
            return result

    # Phase 2: fetch at most 3 forms from the API
    for form in unique_forms[:3]:
        # Skip if already cached (even as a miss)
        if load_cached(cache_dir, form) is not None:
            continue
        result = _try_fetch(form, cache_dir)
        if result is not None:
            return result

    # Mark primary word as miss
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


def build_vocab(*, force: bool = False) -> None:
    """Run the full vocabulary extraction pipeline."""
    # Ensure output directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Check overwrite before doing any work
    if CSV_PATH.exists() and not force:
        print(f"Error: {CSV_PATH} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    print("Loading spaCy model...")
    nlp = spacy.load("de_core_news_lg", exclude=["ner", "parser"])
    nlp.add_pipe("sentencizer")
    nlp.max_length = 2_000_000

    # Load and filter texts
    print("Loading texts...")
    z_text = load_zarathustra(ZARATHUSTRA_PATH)
    w_text = load_wittgenstein(WITTGENSTEIN_PATH)

    print("Filtering non-German passages...")
    z_text = filter_non_german(z_text, nlp)
    w_text = filter_non_german(w_text, nlp)

    # Lemmatize and count
    print("Lemmatizing Zarathustra...")
    z_counts, z_archaic = lemmatize_and_count(z_text, nlp)
    print(f"  {len(z_counts)} unique lemmas")

    print("Lemmatizing Wittgenstein...")
    w_counts, w_archaic = lemmatize_and_count(w_text, nlp)
    print(f"  {len(w_counts)} unique lemmas")

    # Load exclusion set
    print("Loading exclusion set from frequency deck...")
    exclusion = load_exclusion_set(FREQ_DECK_PATH)
    print(f"  {len(exclusion)} forms to exclude")

    # Merge counts and determine source
    all_lemmas: dict[str, dict] = {}
    for lemma, count in z_counts.items():
        all_lemmas[lemma] = {"z": count, "w": 0, "archaic": z_archaic.get(lemma, "")}
    for lemma, count in w_counts.items():
        if lemma in all_lemmas:
            all_lemmas[lemma]["w"] = count
        else:
            all_lemmas[lemma] = {"z": 0, "w": count, "archaic": w_archaic.get(lemma, "")}
        # Prefer archaic form from whichever text had it
        if not all_lemmas[lemma]["archaic"] and lemma in w_archaic:
            all_lemmas[lemma]["archaic"] = w_archaic[lemma]

    # Filter
    candidates = {}
    for lemma, info in all_lemmas.items():
        total = info["z"] + info["w"]
        if total < MIN_FREQUENCY:
            continue
        if lemma.lower() in exclusion:
            continue
        candidates[lemma] = info

    print(f"Candidates after filtering: {len(candidates)}")

    # Fetch Wiktionary definitions
    print("Fetching Wiktionary definitions...")
    cards = []
    for i, (lemma, info) in enumerate(sorted(candidates.items(), key=lambda x: -(x[1]["z"] + x[1]["w"]))):
        total = info["z"] + info["w"]
        source = "both" if info["z"] > 0 and info["w"] > 0 else ("nietzsche" if info["z"] > 0 else "wittgenstein")

        defn = fetch_definition(lemma, CACHE_DIR)

        card = {
            "german": lemma,
            "english": defn["english"] if defn else "",
            "pos": defn["pos"] if defn else "",
            "example_de": defn["example_de"] if defn else "",
            "example_en": defn["example_en"] if defn else "",
            "archaic_form": info["archaic"],
            "source": source,
            "frequency": total,
            "needs_review": "x" if defn is None else "",
        }
        cards.append(card)

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(candidates)} fetched...")

    # Write CSV
    needs_review = sum(1 for c in cards if c["needs_review"])
    print(f"\nWriting {len(cards)} cards to {CSV_PATH} ({needs_review} need review)...")
    write_csv(cards, CSV_PATH, force=force)
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Build German vocabulary CSV from philosophical texts")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cards.csv")
    args = parser.parse_args()
    build_vocab(force=args.force)


if __name__ == "__main__":
    main()
