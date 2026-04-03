"""Tests for srs/generation_import.py — LOS import pipeline."""

import json
import pytest

from knowledge_base.srs.generation_db import (
    init_generation_db,
    get_generation_card,
    update_generation_scheduling,
    update_generation_phase,
)
from knowledge_base.srs.generation_import import import_los, _slugify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_los_data(tmp_path):
    """Create a minimal JSON file with 2 readings, 3 LOS total."""
    data = {
        "deck": "cfa_level1",
        "readings": [
            {
                "number": 1,
                "title": "Rates and Returns",
                "book": 1,
                "los": [
                    {"id": "1.a", "text": "interpret interest rates as required rates of return"},
                    {"id": "1.b", "text": "explain an interest rate as the sum of a real risk-free rate"},
                ],
            },
            {
                "number": 2,
                "title": "Time Value of Money: Future Value and Present Value",
                "book": 1,
                "los": [
                    {"id": "2.a", "text": "interpret interest rates as required rates of return, discounts, or opportunity costs"},
                ],
            },
        ],
    }
    json_path = tmp_path / "cfa_level1_los.json"
    json_path.write_text(json.dumps(data))
    return json_path


# ---------------------------------------------------------------------------
# TestSlugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercases(self):
        assert _slugify("Hello World") == "hello_world"

    def test_replaces_spaces_with_underscores(self):
        assert _slugify("Rates and Returns") == "rates_and_returns"

    def test_strips_colons(self):
        assert _slugify("Time Value: Future") == "time_value_future"

    def test_strips_commas(self):
        assert _slugify("Mean, Median, Mode") == "mean_median_mode"

    def test_multiple_spaces_become_multiple_underscores(self):
        result = _slugify("a  b")
        # Each space is replaced individually
        assert "a" in result and "b" in result

    def test_empty_string(self):
        assert _slugify("") == ""


# ---------------------------------------------------------------------------
# TestImportLos
# ---------------------------------------------------------------------------


class TestImportLos:
    def test_imports_all_cards(self, sample_los_data):
        conn = init_generation_db()
        count = import_los(conn, data_path=sample_los_data)
        assert count == 3

    def test_card_content(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        row = conn.execute(
            "SELECT * FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        assert row is not None
        row = dict(row)

        assert row["deck"] == "cfa_level1"
        assert row["topic_id"] == "1"
        assert row["question"] == "What is LOS 1.a? (Rates and Returns)"
        assert row["answer"] == "interpret interest rates as required rates of return"
        assert row["phase"] == "generation"
        assert row["masking_level"] == 0

    def test_card_content_reading_2(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        row = conn.execute(
            "SELECT * FROM generation_cards WHERE section_id = '2.a'"
        ).fetchone()
        assert row is not None
        row = dict(row)

        assert row["deck"] == "cfa_level1"
        assert row["topic_id"] == "2"
        assert row["question"] == "What is LOS 2.a? (Time Value of Money: Future Value and Present Value)"
        assert "discounts" in row["answer"]

    def test_tags(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        row = conn.execute(
            "SELECT tags FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        tags = json.loads(row["tags"])

        assert "reading::1" in tags
        assert "book::1" in tags

    def test_tags_include_topic_slug(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        row = conn.execute(
            "SELECT tags FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        tags = json.loads(row["tags"])

        # Topic tag should be present and slugified
        topic_tags = [t for t in tags if t.startswith("topic::")]
        assert len(topic_tags) == 1
        assert topic_tags[0] == "topic::rates_and_returns"

    def test_tags_reading_2(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        row = conn.execute(
            "SELECT tags FROM generation_cards WHERE section_id = '2.a'"
        ).fetchone()
        tags = json.loads(row["tags"])

        assert "reading::2" in tags
        assert "book::1" in tags

    def test_idempotent(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)
        import_los(conn, data_path=sample_los_data)

        count = conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        assert count == 3

    def test_preserves_scheduling_on_reimport(self, sample_los_data):
        conn = init_generation_db()
        import_los(conn, data_path=sample_los_data)

        # Simulate some scheduling progress on card 1.a
        row = conn.execute(
            "SELECT card_id FROM generation_cards WHERE section_id = '1.a'"
        ).fetchone()
        card_id = row["card_id"]

        update_generation_scheduling(conn, card_id, {
            "difficulty": 3.5,
            "stability": 7.5,
            "reps": 5,
            "last_review": "2026-01-01T00:00:00",
            "due": "2026-01-08T00:00:00",
        })
        update_generation_phase(conn, card_id, {"masking_level": 2})

        # Re-import
        import_los(conn, data_path=sample_los_data)

        updated = get_generation_card(conn, card_id)
        assert updated["reps"] == 5
        assert updated["masking_level"] == 2
        assert updated["difficulty"] == pytest.approx(3.5)
        assert updated["stability"] == pytest.approx(7.5)
        assert updated["due"] == "2026-01-08T00:00:00"
