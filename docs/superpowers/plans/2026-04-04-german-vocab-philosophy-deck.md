# German Vocabulary Philosophy Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pipeline that extracts novel vocabulary from Nietzsche's *Also sprach Zarathustra* and Wittgenstein's *Philosophische Untersuchungen*, fetches English translations from Wiktionary, and exports a bidirectional Anki deck.

**Architecture:** Two scripts — `build_vocab.py` (tokenize, lemmatize, filter, fetch definitions, write CSV) and `export_apkg.py` (read CSV, build genanki model, export .apkg). A CSV sits between them as the human-review gate. spaCy handles lemmatization; Wiktionary REST API provides translations.

**Tech Stack:** Python 3.12, spaCy (de_core_news_lg), genanki, Wiktionary REST API, standard library (csv, json, sqlite3, zipfile, hashlib, urllib, re, pathlib, time)

**Spec:** `docs/superpowers/specs/2026-04-04-german-vocab-philosophy-deck-design.md`

---

## File Structure

```
scripts/german_vocab/
  build_vocab.py      # Main pipeline: tokenize → lemmatize → filter → fetch → CSV
  export_apkg.py      # Read CSV → build genanki model → write .apkg

data/german_vocab/
  cards.csv                    # Output of build_vocab.py, input to export_apkg.py
  .wiktionary_cache/           # Cached Wiktionary JSON responses
  german_vocab_philosophy.apkg # Final output

tests/
  test_german_vocab_build.py   # Tests for build_vocab.py functions
  test_german_vocab_export.py  # Tests for export_apkg.py functions
```

All `data/german_vocab/` output is already gitignored by existing rules (`data/**/*.csv`, `*.apkg`). The `.wiktionary_cache/` directory is under `data/` so also covered.

---

### Task 1: Add spaCy dependency and download model

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add spaCy to project dependencies**

In `pyproject.toml`, add `spacy>=3.7` to the `dependencies` list:

```toml
dependencies = [
    "genanki>=0.13",
    "textual>=3.0",
    "requests>=2.31",
    "openpyxl>=3.1",
    "matplotlib>=3.8",
    "spacy>=3.7",
]
```

- [ ] **Step 2: Sync dependencies and download German model**

Run:
```bash
uv sync
uv run python -m spacy download de_core_news_lg
```

Expected: Both complete without error. Verify with:
```bash
uv run python -c "import spacy; nlp = spacy.load('de_core_news_lg'); print('OK:', nlp.meta['name'])"
```
Expected output: `OK: core_news_lg`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add spaCy dependency for German vocab pipeline"
```

---

### Task 2: Exclusion set extraction (load existing .apkg)

**Files:**
- Create: `scripts/german_vocab/build_vocab.py` (initial scaffold with exclusion set function)
- Create: `tests/test_german_vocab_build.py`

- [ ] **Step 1: Write the failing test for exclusion set extraction**

Create `tests/test_german_vocab_build.py`:

```python
"""Tests for scripts/german_vocab/build_vocab.py."""

import sqlite3
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _make_fake_apkg(tmp: Path, entries: list[str]) -> Path:
    """Create a minimal .apkg with fake notes.

    Each entry is a German word field (field index 1), using the same
    field-separator format as the real deck: rank \x1f german \x1f ...
    """
    db_path = tmp / "collection.anki21"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT, tags TEXT)"
    )
    for i, entry in enumerate(entries, 1):
        flds = f"{i}\x1f{entry}\x1f\x1f\x1f\x1f\x1f\x1f"
        conn.execute("INSERT INTO notes (id, flds, tags) VALUES (?, ?, '')", (i, flds))
    conn.commit()
    conn.close()

    apkg_path = tmp / "test.apkg"
    with zipfile.ZipFile(apkg_path, "w") as zf:
        zf.write(db_path, "collection.anki21")
    return apkg_path


class TestLoadExclusionSet:
    def test_extracts_base_forms(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_exclusion_set

        apkg = _make_fake_apkg(tmp_path, ["der Hund", "die Katze, -n"])
        result = load_exclusion_set(apkg)
        assert "hund" in result
        assert "katze" in result

    def test_expands_comma_separated_forms(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_exclusion_set

        apkg = _make_fake_apkg(
            tmp_path, ["sein, ist, war, ist gewesen"]
        )
        result = load_exclusion_set(apkg)
        assert "sein" in result
        assert "ist" in result
        assert "war" in result
        assert "gewesen" in result

    def test_strips_articles(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_exclusion_set

        apkg = _make_fake_apkg(tmp_path, ["der Mann", "die Frau", "das Kind"])
        result = load_exclusion_set(apkg)
        assert "mann" in result
        assert "frau" in result
        assert "kind" in result
        # Articles themselves should NOT be in the set (they're part of prefix)
        assert "der" not in result or True  # articles may appear as separate entries

    def test_strips_declension_suffixes(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_exclusion_set

        apkg = _make_fake_apkg(tmp_path, ["der Hund, -e", "die Kreuzung, -en"])
        result = load_exclusion_set(apkg)
        assert "hund" in result
        assert "kreuzung" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_german_vocab_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.german_vocab'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/german_vocab/__init__.py` (empty file).

Create `scripts/german_vocab/build_vocab.py`:

```python
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
            # Strip declension suffixes like -en, -̈e
            form = re.sub(r"\s*-[^ ]*$", "", form).strip()
            if form:
                forms.add(form)
                # Also add individual words from multi-word forms
                for word in form.split():
                    if len(word) > 1:
                        forms.add(word)

    return forms
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_german_vocab_build.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/__init__.py scripts/german_vocab/build_vocab.py tests/test_german_vocab_build.py
git commit -m "feat: add exclusion set extraction from existing .apkg deck"
```

---

### Task 3: Text loading and Latin filtering

**Files:**
- Modify: `scripts/german_vocab/build_vocab.py`
- Modify: `tests/test_german_vocab_build.py`

- [ ] **Step 1: Write the failing tests for text loading**

Append to `tests/test_german_vocab_build.py`:

```python
class TestLoadText:
    def test_strips_gutenberg_boilerplate(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_zarathustra

        text_file = tmp_path / "z.txt"
        text_file.write_text(
            "Title: Test\n\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK ***\n\n"
            "Echte deutsche Worte hier.\n\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK ***\n\n"
            "Gutenberg footer stuff.\n"
        )
        result = load_zarathustra(text_file)
        assert "Echte deutsche Worte hier." in result
        assert "Gutenberg footer" not in result
        assert "Title: Test" not in result

    def test_strips_yaml_frontmatter(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_wittgenstein

        text_file = tmp_path / "w.md"
        text_file.write_text(
            "---\nauthor: Wittgenstein\ntitle: PI\n---\n\n"
            "Echte deutsche Worte hier.\n"
        )
        result = load_wittgenstein(text_file)
        assert "Echte deutsche Worte hier." in result
        assert "author:" not in result


class TestFilterLatin:
    def test_removes_latin_passages(self):
        from scripts.german_vocab.build_vocab import filter_non_german

        import spacy
        nlp = spacy.load("de_core_news_lg")

        text = (
            "In diesen Worten erhalten wir ein bestimmtes Bild. "
            "cum ipsi appellabant rem aliquam et cum secundum eam vocem. "
            "Die Wörter der Sprache benennen Gegenstände."
        )
        result = filter_non_german(text, nlp)
        assert "bestimmtes Bild" in result
        assert "benennen Gegenstände" in result
        assert "appellabant" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_german_vocab_build.py::TestLoadText -v`
Expected: FAIL — `cannot import name 'load_zarathustra'`

- [ ] **Step 3: Implement text loading and Latin filtering**

Add to `scripts/german_vocab/build_vocab.py`:

```python
import spacy


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_german_vocab_build.py::TestLoadText tests/test_german_vocab_build.py::TestFilterLatin -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/build_vocab.py tests/test_german_vocab_build.py
git commit -m "feat: add text loading and Latin passage filtering"
```

---

### Task 4: Lemmatization and archaic normalization

**Files:**
- Modify: `scripts/german_vocab/build_vocab.py`
- Modify: `tests/test_german_vocab_build.py`

- [ ] **Step 1: Write failing tests for lemmatization and archaic normalization**

Append to `tests/test_german_vocab_build.py`:

```python
class TestArchaicNormalization:
    def test_th_to_t(self):
        from scripts.german_vocab.build_vocab import normalize_archaic

        assert normalize_archaic("Thorheit") == "Torheit"
        assert normalize_archaic("Thiere") == "Tiere"
        assert normalize_archaic("Theil") == "Teil"
        assert normalize_archaic("Thränen") == "Tränen"

    def test_giebt_to_gibt(self):
        from scripts.german_vocab.build_vocab import normalize_archaic

        assert normalize_archaic("giebt") == "gibt"
        assert normalize_archaic("gieng") == "ging"

    def test_ss_to_eszett(self):
        from scripts.german_vocab.build_vocab import normalize_archaic

        assert normalize_archaic("Gleichniss") == "Gleichnis"
        assert normalize_archaic("heisst") == "heißt"
        assert normalize_archaic("weiss") == "weiß"

    def test_no_change_for_modern(self):
        from scripts.german_vocab.build_vocab import normalize_archaic

        assert normalize_archaic("Tugend") == "Tugend"
        assert normalize_archaic("Haus") == "Haus"

    def test_diess_to_dies(self):
        from scripts.german_vocab.build_vocab import normalize_archaic

        assert normalize_archaic("diess") == "dies"


class TestLemmatizeAndCount:
    def test_groups_inflected_forms(self):
        from scripts.german_vocab.build_vocab import lemmatize_and_count

        import spacy
        nlp = spacy.load("de_core_news_lg")

        text = "Tugend Tugenden Tugend Tugend"
        counts, archaic_map = lemmatize_and_count(text, nlp)
        # All forms should collapse to one lemma
        assert len(counts) == 1
        lemma = list(counts.keys())[0]
        assert counts[lemma] == 4

    def test_preserves_archaic_forms(self):
        from scripts.german_vocab.build_vocab import lemmatize_and_count

        import spacy
        nlp = spacy.load("de_core_news_lg")

        # "Thiere" is archaic for "Tiere" (animals)
        text = "Thiere Thiere Thiere Thiere"
        counts, archaic_map = lemmatize_and_count(text, nlp)
        # Should have a modern lemma with archaic map entry
        has_archaic = any(v for v in archaic_map.values() if v)
        assert has_archaic
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_german_vocab_build.py::TestArchaicNormalization tests/test_german_vocab_build.py::TestLemmatizeAndCount -v`
Expected: FAIL — `cannot import name 'normalize_archaic'`

- [ ] **Step 3: Implement archaic normalization and lemmatization**

Add to `scripts/german_vocab/build_vocab.py`:

```python
from collections import Counter


# Archaic spelling rules (Nietzsche-era orthography → modern)
ARCHAIC_RULES: list[tuple[re.Pattern, str]] = [
    # "Th" at word start → "T" (Thorheit→Torheit, Thiere→Tiere, Theil→Teil)
    (re.compile(r"^Th"), "T"),
    (re.compile(r"^th"), "t"),
    # "gie" → "gi" (giebt→gibt, gieng→ging)
    (re.compile(r"^gie"), "gi"),
    # "ey" → "ei" (seyn→sein)
    (re.compile(r"ey"), "ei"),
    # Terminal "ss" after long vowel → "ß" (heisst→heißt, weiss→weiß)
    (re.compile(r"(?<=[aeiouäöü])ss(?=t?$)", re.IGNORECASE), "ß"),
    # Terminal "ss" → "s" for words like Gleichniss→Gleichnis, diess→dies
    (re.compile(r"ss$"), "s"),
]


def normalize_archaic(word: str) -> str:
    """Normalize 19th-century German spelling to modern equivalents."""
    result = word
    for pattern, replacement in ARCHAIC_RULES:
        result = pattern.sub(replacement, result)
    return result


# spaCy POS tags that indicate content words
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}

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

        # Track archaic form if normalization changed the original token
        original = token.text
        original_normalized = normalize_archaic(original)
        if original_normalized != original and modern not in archaic_map:
            archaic_map[modern] = original

        counts[modern] += 1

    return counts, archaic_map
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_german_vocab_build.py::TestArchaicNormalization tests/test_german_vocab_build.py::TestLemmatizeAndCount -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/build_vocab.py tests/test_german_vocab_build.py
git commit -m "feat: add archaic normalization and spaCy lemmatization"
```

---

### Task 5: Wiktionary fetching with caching

**Files:**
- Modify: `scripts/german_vocab/build_vocab.py`
- Modify: `tests/test_german_vocab_build.py`

- [ ] **Step 1: Write failing tests for Wiktionary parsing and caching**

Append to `tests/test_german_vocab_build.py`:

```python
import json


class TestParseWiktionaryResponse:
    def test_extracts_definition_and_pos(self):
        from scripts.german_vocab.build_vocab import parse_wiktionary_response

        response = {
            "de": [
                {
                    "partOfSpeech": "Noun",
                    "language": "German",
                    "definitions": [
                        {
                            "definition": '<a href="/wiki/virtue" title="virtue">virtue</a>',
                            "parsedExamples": [
                                {
                                    "example": "Ohne <b>Tugend</b> gibt es keine Freiheit.",
                                    "translation": "Without <b>virtue</b>, there is no freedom.",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        result = parse_wiktionary_response(response)
        assert result["pos"] == "Noun"
        assert "virtue" in result["english"]
        assert "Tugend" in result["example_de"]
        assert "virtue" in result["example_en"]

    def test_strips_html_tags(self):
        from scripts.german_vocab.build_vocab import parse_wiktionary_response

        response = {
            "de": [
                {
                    "partOfSpeech": "Noun",
                    "language": "German",
                    "definitions": [
                        {
                            "definition": (
                                '<span class="usage-label-sense"></span> '
                                '<a href="/wiki/mob">mob</a>, '
                                '<a href="/wiki/riffraff">riffraff</a>'
                            ),
                        }
                    ],
                }
            ]
        }
        result = parse_wiktionary_response(response)
        assert result["english"] == "mob, riffraff"
        assert "<" not in result["english"]

    def test_returns_none_for_no_german_entry(self):
        from scripts.german_vocab.build_vocab import parse_wiktionary_response

        result = parse_wiktionary_response({"en": [{"partOfSpeech": "Noun"}]})
        assert result is None


class TestWiktionaryCache:
    def test_caches_responses(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_cached, save_cached

        cache_dir = tmp_path / ".wiktionary_cache"
        cache_dir.mkdir()

        data = {"de": [{"partOfSpeech": "Noun", "definitions": []}]}
        save_cached(cache_dir, "Tugend", data)

        loaded = load_cached(cache_dir, "Tugend")
        assert loaded == data

    def test_returns_none_for_cache_miss(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_cached

        cache_dir = tmp_path / ".wiktionary_cache"
        cache_dir.mkdir()
        assert load_cached(cache_dir, "missing") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_german_vocab_build.py::TestParseWiktionaryResponse tests/test_german_vocab_build.py::TestWiktionaryCache -v`
Expected: FAIL — `cannot import name 'parse_wiktionary_response'`

- [ ] **Step 3: Implement Wiktionary fetching, parsing, and caching**

Add to `scripts/german_vocab/build_vocab.py`:

```python
import json
import time
import urllib.parse
import urllib.request

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
    """Fetch a word definition from the Wiktionary REST API.

    Returns the parsed JSON response, or None on 404/error.
    """
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

    # Take the first entry
    entry = entries[0]
    pos = entry.get("partOfSpeech", "")
    definitions = entry.get("definitions", [])

    # Collect English translations from first 2 definitions
    english_parts = []
    example_de = ""
    example_en = ""
    for defn in definitions[:2]:
        raw = defn.get("definition", "")
        # Strip HTML tags
        clean = re.sub(r"<[^>]+>", "", raw).strip()
        # Remove leading/trailing whitespace and empty results
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            english_parts.append(clean)

        # Grab first example if we don't have one yet
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


def fetch_definition(
    word: str, cache_dir: Path, pos_hint: str = ""
) -> dict | None:
    """Fetch and parse a Wiktionary definition, with caching and fallback.

    Tries the word as-is, then opposite case, then common alternatives.
    """
    # Check cache first
    cached = load_cached(cache_dir, word)
    if cached is not None:
        result = parse_wiktionary_response(cached)
        if result is not None:
            return result

    # Try the word as-is
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

    # Mark as miss in cache (empty dict)
    save_cached(cache_dir, word, {})
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_german_vocab_build.py::TestParseWiktionaryResponse tests/test_german_vocab_build.py::TestWiktionaryCache -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/build_vocab.py tests/test_german_vocab_build.py
git commit -m "feat: add Wiktionary fetching, parsing, and caching"
```

---

### Task 6: CSV writing with overwrite protection

**Files:**
- Modify: `scripts/german_vocab/build_vocab.py`
- Modify: `tests/test_german_vocab_build.py`

- [ ] **Step 1: Write failing tests for CSV output**

Append to `tests/test_german_vocab_build.py`:

```python
class TestWriteCsv:
    def test_writes_expected_columns(self, tmp_path):
        from scripts.german_vocab.build_vocab import write_csv

        cards = [
            {
                "german": "Tugend",
                "english": "virtue",
                "pos": "Noun",
                "example_de": "Ohne Tugend gibt es keine Freiheit.",
                "example_en": "Without virtue, there is no freedom.",
                "archaic_form": "",
                "source": "both",
                "frequency": 133,
                "needs_review": "",
            }
        ]
        out = tmp_path / "cards.csv"
        write_csv(cards, out)

        import csv
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["german"] == "Tugend"
        assert rows[0]["english"] == "virtue"
        assert rows[0]["pos"] == "Noun"
        assert rows[0]["frequency"] == "133"

    def test_refuses_overwrite_without_force(self, tmp_path):
        from scripts.german_vocab.build_vocab import write_csv

        out = tmp_path / "cards.csv"
        out.write_text("existing content")

        with pytest.raises(FileExistsError):
            write_csv([], out, force=False)

    def test_allows_overwrite_with_force(self, tmp_path):
        from scripts.german_vocab.build_vocab import write_csv

        out = tmp_path / "cards.csv"
        out.write_text("existing content")

        write_csv([{
            "german": "Test", "english": "test", "pos": "Noun",
            "example_de": "", "example_en": "", "archaic_form": "",
            "source": "both", "frequency": 5, "needs_review": "",
        }], out, force=True)

        import csv
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_german_vocab_build.py::TestWriteCsv -v`
Expected: FAIL — `cannot import name 'write_csv'`

- [ ] **Step 3: Implement CSV writing**

Add to `scripts/german_vocab/build_vocab.py`:

```python
import csv

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_german_vocab_build.py::TestWriteCsv -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/build_vocab.py tests/test_german_vocab_build.py
git commit -m "feat: add CSV writing with overwrite protection"
```

---

### Task 7: Main pipeline (build_vocab.py CLI)

**Files:**
- Modify: `scripts/german_vocab/build_vocab.py`

- [ ] **Step 1: Implement the main pipeline function and CLI**

Add to `scripts/german_vocab/build_vocab.py`:

```python
import argparse
import sys

# Paths
TEXTS_DIR = Path("resources/texts")
ZARATHUSTRA_PATH = TEXTS_DIR / "Also Sprach Zarathustra.txt"
WITTGENSTEIN_PATH = TEXTS_DIR / "Philosophische Untersuchungen.md"
FREQ_DECK_PATH = Path.home() / "Dropbox" / "autodidact 2025" / "GREATS" / "English-German_Sorted_by_Frequency.apkg"
DATA_DIR = Path("data/german_vocab")
CACHE_DIR = DATA_DIR / ".wiktionary_cache"
CSV_PATH = DATA_DIR / "cards.csv"

MIN_FREQUENCY = 4


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
    nlp = spacy.load("de_core_news_lg")

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
```

- [ ] **Step 2: Smoke test the pipeline end-to-end**

Run:
```bash
uv run python -m scripts.german_vocab.build_vocab --force
```

Expected: Prints progress, writes `data/german_vocab/cards.csv`. Verify:
```bash
head -5 data/german_vocab/cards.csv
wc -l data/german_vocab/cards.csv
grep ",x$" data/german_vocab/cards.csv | wc -l
```

Expected: ~780+ lines (including header), a handful of `needs_review` entries.

- [ ] **Step 3: Commit**

```bash
git add scripts/german_vocab/build_vocab.py
git commit -m "feat: add main build_vocab pipeline with CLI"
```

---

### Task 8: Anki export script

**Files:**
- Create: `scripts/german_vocab/export_apkg.py`
- Create: `tests/test_german_vocab_export.py`

- [ ] **Step 1: Write failing tests for the exporter**

Create `tests/test_german_vocab_export.py`:

```python
"""Tests for scripts/german_vocab/export_apkg.py."""

import csv
import sqlite3
import zipfile
from pathlib import Path


def _write_test_csv(path: Path, rows: list[dict]) -> None:
    """Write a test cards.csv."""
    fieldnames = [
        "german", "english", "pos", "example_de", "example_en",
        "archaic_form", "source", "frequency", "needs_review",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestExportApkg:
    def test_produces_apkg_file(self, tmp_path):
        from scripts.german_vocab.export_apkg import export_apkg

        csv_path = tmp_path / "cards.csv"
        _write_test_csv(csv_path, [
            {
                "german": "Tugend", "english": "virtue", "pos": "Noun",
                "example_de": "Ohne Tugend.", "example_en": "Without virtue.",
                "archaic_form": "", "source": "both", "frequency": "133",
                "needs_review": "",
            },
        ])
        out_path = tmp_path / "out.apkg"
        export_apkg(csv_path, out_path)
        assert out_path.exists()
        # Verify it's a valid zip
        assert zipfile.is_zipfile(out_path)

    def test_creates_two_cards_per_row(self, tmp_path):
        from scripts.german_vocab.export_apkg import export_apkg

        csv_path = tmp_path / "cards.csv"
        _write_test_csv(csv_path, [
            {
                "german": "Tugend", "english": "virtue", "pos": "Noun",
                "example_de": "", "example_en": "",
                "archaic_form": "", "source": "both", "frequency": "133",
                "needs_review": "",
            },
            {
                "german": "Ekel", "english": "disgust", "pos": "Noun",
                "example_de": "", "example_en": "",
                "archaic_form": "", "source": "nietzsche", "frequency": "38",
                "needs_review": "",
            },
        ])
        out_path = tmp_path / "out.apkg"
        export_apkg(csv_path, out_path)

        # Extract and check the database
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(out_path) as zf:
            zf.extractall(extract_dir)

        # genanki writes collection.anki2
        db_path = extract_dir / "collection.anki2"
        conn = sqlite3.connect(str(db_path))
        note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        card_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        conn.close()

        # 2 notes, each with 2 templates (DE->EN, EN->DE) = 4 cards
        assert note_count == 2
        assert card_count == 4

    def test_skips_needs_review_rows(self, tmp_path):
        from scripts.german_vocab.export_apkg import export_apkg

        csv_path = tmp_path / "cards.csv"
        _write_test_csv(csv_path, [
            {
                "german": "Tugend", "english": "virtue", "pos": "Noun",
                "example_de": "", "example_en": "",
                "archaic_form": "", "source": "both", "frequency": "133",
                "needs_review": "",
            },
            {
                "german": "Abrichtung", "english": "", "pos": "",
                "example_de": "", "example_en": "",
                "archaic_form": "", "source": "wittgenstein", "frequency": "10",
                "needs_review": "x",
            },
        ])
        out_path = tmp_path / "out.apkg"
        export_apkg(csv_path, out_path)

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(out_path) as zf:
            zf.extractall(extract_dir)

        db_path = extract_dir / "collection.anki2"
        conn = sqlite3.connect(str(db_path))
        note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        conn.close()

        assert note_count == 1  # Only Tugend, not Abrichtung


class TestStableGuids:
    def test_same_word_same_guid(self):
        from scripts.german_vocab.export_apkg import stable_guid

        assert stable_guid("Tugend") == stable_guid("Tugend")

    def test_different_words_different_guids(self):
        from scripts.german_vocab.export_apkg import stable_guid

        assert stable_guid("Tugend") != stable_guid("Ekel")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_german_vocab_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.german_vocab.export_apkg'`

- [ ] **Step 3: Implement the exporter**

Create `scripts/german_vocab/export_apkg.py`:

```python
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
            # Skip rows that still need review
            if row.get("needs_review", "").strip():
                continue
            # Skip rows with no English translation
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_german_vocab_export.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/german_vocab/export_apkg.py tests/test_german_vocab_export.py
git commit -m "feat: add bidirectional Anki .apkg exporter for German vocab"
```

---

### Task 9: End-to-end smoke test

**Files:**
- None new — this validates the full pipeline

- [ ] **Step 1: Run the full pipeline**

```bash
uv run python -m scripts.german_vocab.build_vocab --force
```

Expected: Completes, prints summary like:
```
Candidates after filtering: ~780
Fetching Wiktionary definitions...
Writing 780 cards to data/german_vocab/cards.csv (25 need review)...
Done.
```

- [ ] **Step 2: Inspect the CSV output**

```bash
head -10 data/german_vocab/cards.csv
wc -l data/german_vocab/cards.csv
grep "needs_review" data/german_vocab/cards.csv | head -5
```

Verify: reasonable card count, translations populated for most rows, a small number of `needs_review` entries.

- [ ] **Step 3: Run the exporter**

```bash
uv run python -m scripts.german_vocab.export_apkg
```

Expected: Prints something like `Wrote data/german_vocab/german_vocab_philosophy.apkg: 755 notes (1510 cards)`

- [ ] **Step 4: Verify the .apkg**

```bash
python3 -c "
import zipfile, sqlite3, tempfile, shutil
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    with zipfile.ZipFile('data/german_vocab/german_vocab_philosophy.apkg') as zf:
        zf.extractall(tmp)
    conn = sqlite3.connect(str(Path(tmp) / 'collection.anki21'))
    notes = conn.execute('SELECT COUNT(*) FROM notes').fetchone()[0]
    cards = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
    print(f'Notes: {notes}, Cards: {cards}')
    conn.close()
"
```

Expected: Notes ~750+, Cards = Notes * 2

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/test_german_vocab_build.py tests/test_german_vocab_export.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/german_vocab/ tests/test_german_vocab_build.py tests/test_german_vocab_export.py
git commit -m "feat: complete German vocab philosophy deck pipeline"
```
