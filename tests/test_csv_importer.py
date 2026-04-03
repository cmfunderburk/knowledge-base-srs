"""Tests for CSV import of exact-answer cards."""

import csv
from pathlib import Path

import pytest

from knowledge_base.srs.csv_importer import parse_csv, import_csv
from knowledge_base.srs.generation_db import init_generation_db


def _write_csv(tmp_path, filename, rows, fieldnames=None):
    """Write rows to a CSV file and return the path."""
    path = tmp_path / filename
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestParseCsv:
    def test_basic_parse(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "What is X?", "answer": "42"},
            {"question": "What is Y?", "answer": "7.5"},
        ])
        cards = parse_csv(path, deck="test", source="src", topic="t")
        assert len(cards) == 2
        assert cards[0]["question"] == "What is X?"
        assert cards[0]["answer"] == "42"

    def test_card_type_is_exact(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["card_type"] == "exact"

    def test_card_index_auto_assigned(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"},
            {"question": "Q3?", "answer": "A3"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert [c["card_index"] for c in cards] == [0, 1, 2]

    def test_topic_from_csv_column(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "topic": "custom_topic"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="default")
        assert cards[0]["topic_id"] == "custom_topic"

    def test_topic_falls_back_to_arg(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="fallback")
        assert cards[0]["topic_id"] == "fallback"

    def test_section_from_csv_column(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "section": "2.1"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["section_id"] == "2.1"

    def test_section_defaults_to_1(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["section_id"] == "1"

    def test_card_index_per_section(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "A1", "section": "a"},
            {"question": "Q2?", "answer": "A2", "section": "b"},
            {"question": "Q3?", "answer": "A3", "section": "a"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        a_cards = [c for c in cards if c["section_id"] == "a"]
        b_cards = [c for c in cards if c["section_id"] == "b"]
        assert [c["card_index"] for c in a_cards] == [0, 1]
        assert [c["card_index"] for c in b_cards] == [0]

    def test_tags_json_array(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "tags": '["econ", "gdp"]'},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        assert cards[0]["tags"] == '["econ", "gdp"]'

    def test_tags_comma_separated(self, tmp_path):
        import json
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "A", "tags": "econ, gdp"},
        ])
        cards = parse_csv(path, deck="d", source="s", topic="t")
        parsed = json.loads(cards[0]["tags"])
        assert parsed == ["econ", "gdp"]

    def test_missing_question_column_raises(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"answer": "A"},
        ], fieldnames=["answer"])
        with pytest.raises(ValueError, match="question"):
            parse_csv(path, deck="d", source="s", topic="t")

    def test_missing_answer_column_raises(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?"},
        ], fieldnames=["question"])
        with pytest.raises(ValueError, match="answer"):
            parse_csv(path, deck="d", source="s", topic="t")


class TestImportCsv:
    def test_import_creates_cards_in_db(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q1?", "answer": "42"},
            {"question": "Q2?", "answer": "7.5"},
        ])
        conn = init_generation_db()
        n = import_csv(conn, path, deck="test", source="src", topic="t")
        assert n == 2

    def test_import_cards_are_exact_type(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s", topic="t")
        card = conn.execute(
            "SELECT card_type FROM generation_cards"
        ).fetchone()
        assert card["card_type"] == "exact"

    def test_import_idempotent(self, tmp_path):
        path = _write_csv(tmp_path, "test.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s", topic="t")
        n2 = import_csv(conn, path, deck="d", source="s", topic="t")
        assert n2 == 1
        total = conn.execute("SELECT COUNT(*) FROM generation_cards").fetchone()[0]
        assert total == 1

    def test_import_topic_from_filename(self, tmp_path):
        path = _write_csv(tmp_path, "gdp_data.csv", [
            {"question": "Q?", "answer": "42"},
        ])
        conn = init_generation_db()
        import_csv(conn, path, deck="d", source="s")
        card = conn.execute("SELECT topic_id FROM generation_cards").fetchone()
        assert card["topic_id"] == "gdp_data"
