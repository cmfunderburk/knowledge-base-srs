"""Tests for srs/importer.py — CSV import into the SRS database."""

import json
from pathlib import Path

import pytest

from knowledge_base.srs.db import init_db
from knowledge_base.srs.importer import import_deck, _find_entity_config, _load_desc_stats

FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn():
    return init_db()


def _run_import(conn, data_dir=None, desc_stats_dir=None):
    """Helper that runs import_deck with the sample fixture data."""
    return import_deck(
        conn,
        deck_key="development",
        data_dir=data_dir or FIXTURES,
        desc_stats_dir=desc_stats_dir or FIXTURES,
        desc_stats_prefix="desc_stats_",
    )


# ---------------------------------------------------------------------------
# TestFindEntityConfig
# ---------------------------------------------------------------------------

class TestFindEntityConfig:
    def test_finds_by_name(self):
        entities = [
            {"name": "India", "entity_type": "major", "tag_slug": "india"},
            {"name": "World", "entity_type": "region", "tag_slug": "world"},
        ]
        result = _find_entity_config("India", entities)
        assert result is not None
        assert result["tag_slug"] == "india"

    def test_returns_none_when_missing(self):
        entities = [{"name": "India", "entity_type": "major", "tag_slug": "india"}]
        assert _find_entity_config("Brazil", entities) is None

    def test_empty_list(self):
        assert _find_entity_config("India", []) is None


# ---------------------------------------------------------------------------
# TestLoadDescStats
# ---------------------------------------------------------------------------

class TestLoadDescStats:
    def test_loads_mean_and_std(self):
        result = _load_desc_stats(FIXTURES, "gdp_pc_ppp", prefix="desc_stats_")
        assert result is not None
        assert result["mean"] == pytest.approx(27833.0)
        assert result["std"] == pytest.approx(27142.0)

    def test_returns_none_for_missing_file(self, tmp_path):
        result = _load_desc_stats(tmp_path, "nonexistent", prefix="")
        assert result is None

    def test_no_prefix(self, tmp_path):
        # Write a file without prefix
        csv_path = tmp_path / "some_indicator.csv"
        csv_path.write_text(
            "indicator_id,mean,std\nsome_indicator,100.0,20.0\n"
        )
        result = _load_desc_stats(tmp_path, "some_indicator", prefix="")
        assert result is not None
        assert result["mean"] == pytest.approx(100.0)
        assert result["std"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# TestImportDeckCountry
# ---------------------------------------------------------------------------

class TestImportDeckCountryRows:
    def test_imports_country_rows_only(self):
        """India + USA imported; World and South Asia (region) excluded."""
        conn = _make_conn()
        count = _run_import(conn)
        assert count == 2

    def test_world_not_in_db(self):
        conn = _make_conn()
        _run_import(conn)
        rows = conn.execute(
            "SELECT * FROM cards WHERE entity = 'World'"
        ).fetchall()
        assert len(rows) == 0

    def test_south_asia_not_in_db(self):
        conn = _make_conn()
        _run_import(conn)
        rows = conn.execute(
            "SELECT * FROM cards WHERE entity = 'South Asia'"
        ).fetchall()
        assert len(rows) == 0

    def test_india_in_db(self):
        conn = _make_conn()
        _run_import(conn)
        row = conn.execute(
            "SELECT * FROM cards WHERE entity = 'India'"
        ).fetchone()
        assert row is not None

    def test_usa_in_db(self):
        conn = _make_conn()
        _run_import(conn)
        row = conn.execute(
            "SELECT * FROM cards WHERE entity = 'USA'"
        ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# TestCardFieldsPopulated
# ---------------------------------------------------------------------------

class TestCardFieldsPopulated:
    def _get_india_card(self, conn):
        row = conn.execute(
            "SELECT * FROM cards WHERE entity = 'India'"
        ).fetchone()
        assert row is not None, "India card not found"
        return dict(row)

    def test_question_populated(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert "India" in card["question"]
        assert "GDP per capita (PPP)" in card["question"]
        assert "2024" in card["question"]

    def test_answer_in_display_units(self):
        """scale_factor=1 for gdp_pc_ppp, so answer == raw value."""
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["answer"] == pytest.approx(2389.0)

    def test_indicator_mean_populated(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["indicator_mean"] == pytest.approx(27833.0)

    def test_indicator_std_populated(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["indicator_std"] == pytest.approx(27142.0)

    def test_state_is_new(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["state"] == "new"

    def test_deck_field(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["deck"] == "development"

    def test_indicator_id_field(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["indicator_id"] == "gdp_pc_ppp"

    def test_era_field(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["era"] == "current"

    def test_unit_prefix(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        assert card["unit_prefix"] == "$"

    def test_tags_is_json_list(self):
        conn = _make_conn()
        _run_import(conn)
        card = self._get_india_card(conn)
        tags = json.loads(card["tags"])
        assert isinstance(tags, list)
        assert len(tags) > 0


# ---------------------------------------------------------------------------
# TestIdempotentReimport
# ---------------------------------------------------------------------------

class TestIdempotentReimport:
    def test_second_import_returns_same_count(self):
        conn = _make_conn()
        first = _run_import(conn)
        second = _run_import(conn)
        assert first == 2
        assert second == 2

    def test_no_duplicates_after_reimport(self):
        conn = _make_conn()
        _run_import(conn)
        _run_import(conn)
        rows = conn.execute("SELECT COUNT(*) FROM cards").fetchone()
        assert rows[0] == 2

    def test_scheduling_preserved_on_reimport(self):
        """Scheduling state set after first import must survive a re-import."""
        from knowledge_base.srs.db import update_card_scheduling

        conn = _make_conn()
        _run_import(conn)

        # Simulate reviewing India's card
        card_id = conn.execute(
            "SELECT card_id FROM cards WHERE entity = 'India'"
        ).fetchone()[0]
        update_card_scheduling(conn, card_id, {
            "state": "review",
            "reps": 3,
            "stability": 7.5,
        })

        # Re-import
        _run_import(conn)

        # Scheduling should be preserved
        row = dict(conn.execute(
            "SELECT * FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone())
        assert row["state"] == "review"
        assert row["reps"] == 3
        assert row["stability"] == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# TestNotesIncludeReferenceData
# ---------------------------------------------------------------------------

class TestNotesIncludeReferenceData:
    def test_notes_contain_world_avg(self):
        conn = _make_conn()
        _run_import(conn)
        card = dict(conn.execute(
            "SELECT notes FROM cards WHERE entity = 'India'"
        ).fetchone())
        assert "World avg" in card["notes"]

    def test_notes_contain_regional_avg(self):
        """India is in South Asia which has a value in the fixture CSV."""
        conn = _make_conn()
        _run_import(conn)
        card = dict(conn.execute(
            "SELECT notes FROM cards WHERE entity = 'India'"
        ).fetchone())
        # South Asia has value 7200 in fixture; should appear as regional avg
        assert "regional avg" in card["notes"]

    def test_notes_contain_source(self):
        conn = _make_conn()
        _run_import(conn)
        card = dict(conn.execute(
            "SELECT notes FROM cards WHERE entity = 'India'"
        ).fetchone())
        assert "World Bank WDI" in card["notes"]

    def test_usa_notes_no_regional_avg(self):
        """USA's region is 'Europe & Central Asia' but the fixture has no
        matching region entity (region entities must have entity_type='region').
        The fixture South Asia row is entity_type=region but not E&CA, so
        USA gets no regional avg."""
        conn = _make_conn()
        _run_import(conn)
        card = dict(conn.execute(
            "SELECT notes FROM cards WHERE entity = 'USA'"
        ).fetchone())
        # World avg is always present
        assert "World avg" in card["notes"]
