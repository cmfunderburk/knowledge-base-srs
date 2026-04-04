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
