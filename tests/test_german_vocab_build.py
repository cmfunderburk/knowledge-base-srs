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

    def test_strips_declension_suffixes(self, tmp_path):
        from scripts.german_vocab.build_vocab import load_exclusion_set

        apkg = _make_fake_apkg(tmp_path, ["der Hund, -e", "die Kreuzung, -en"])
        result = load_exclusion_set(apkg)
        assert "hund" in result
        assert "kreuzung" in result


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
