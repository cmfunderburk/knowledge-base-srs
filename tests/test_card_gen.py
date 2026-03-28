"""Tests for card_gen.py — pure card generation helpers."""

import pytest
from knowledge_base.card_gen import (
    _format_number,
    build_tags,
    format_answer,
    generate_notes,
    generate_notes_land_area,
    generate_question,
)


# ---------------------------------------------------------------------------
# format_answer
# ---------------------------------------------------------------------------

def test_format_answer_with_scale_factor():
    indicator = {"decimals": 1, "scale_factor": 1_000_000_000}
    assert format_answer(2_345_000_000, indicator) == "2.3"


def test_format_answer_default_scale_factor():
    indicator = {"decimals": 0}
    assert format_answer(8379, indicator) == "8379"


def test_format_answer_two_decimals():
    indicator = {"decimals": 2, "scale_factor": 1}
    assert format_answer(3.14159, indicator) == "3.14"


def test_format_answer_rounds_correctly():
    indicator = {"decimals": 1}
    assert format_answer(1.25, indicator) == "1.2"  # Python rounds half to even


def test_format_answer_large_integer():
    indicator = {"decimals": 0, "scale_factor": 1}
    assert format_answer(1_000_000, indicator) == "1000000"


# ---------------------------------------------------------------------------
# generate_question
# ---------------------------------------------------------------------------

def test_generate_question_current_era():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=2022,
        unit_label="in 2021 international dollars",
        era="current",
    )
    assert q == "What is India's GDP per capita (PPP) as of 2022, in 2021 international dollars?"


def test_generate_question_historical_era():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=1990,
        unit_label="in 2021 international dollars",
        era="1990",
    )
    assert q == "What was India's GDP per capita (PPP) in 1990, in 2021 international dollars?"


def test_generate_question_uses_is_for_current():
    q = generate_question(
        entity="Brazil",
        indicator_name="life expectancy",
        year=2023,
        unit_label="years",
        era="current",
    )
    assert q.startswith("What is")


def test_generate_question_uses_was_for_non_current():
    q = generate_question(
        entity="Brazil",
        indicator_name="life expectancy",
        year=2000,
        unit_label="years",
        era="2000",
    )
    assert q.startswith("What was")


# ---------------------------------------------------------------------------
# _format_number (private helper, tested indirectly via generate_notes but
# also useful to test directly for edge cases)
# ---------------------------------------------------------------------------

def test_format_number_no_prefix_integer():
    assert _format_number(17500) == "17,500"


def test_format_number_with_prefix():
    assert _format_number(17500, prefix="$") == "$17,500"


def test_format_number_with_decimals():
    assert _format_number(1234.5, prefix="", decimals=1) == "1,234.5"


def test_format_number_zero_decimals_shows_no_decimal_point():
    result = _format_number(100.9, decimals=0)
    assert "." not in result
    assert result == "101"


# ---------------------------------------------------------------------------
# generate_notes
# ---------------------------------------------------------------------------

def test_generate_notes_with_world_and_regional_avg():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=7200,
        unit_prefix="$",
    )
    assert "Source: World Bank WDI" in notes
    assert "World avg: $17,500" in notes
    assert "regional avg: $7,200" in notes


def test_generate_notes_world_avg_only():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=None,
        unit_prefix="$",
    )
    assert "World avg: $17,500" in notes
    assert "regional avg" not in notes


def test_generate_notes_no_world_avg():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=None,
        regional_avg=None,
        unit_prefix="$",
    )
    assert notes == "Source: World Bank WDI"
    assert "World avg" not in notes


def test_generate_notes_pipe_separator():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=100,
        regional_avg=None,
        unit_prefix="",
    )
    assert " | " in notes


def test_generate_notes_decimals():
    notes = generate_notes(
        source="test",
        world_avg=1.5,
        regional_avg=1.2,
        unit_prefix="",
        decimals=1,
    )
    assert "1.5" in notes
    assert "1.2" in notes


# ---------------------------------------------------------------------------
# generate_notes_land_area
# ---------------------------------------------------------------------------

def test_generate_notes_land_area_format():
    notes = generate_notes_land_area(
        source="World Bank WDI",
        reference_total=30_370_000,
    )
    assert "Source: World Bank WDI" in notes
    assert "30,370,000" in notes
    assert "km²" in notes


def test_generate_notes_land_area_float_input():
    notes = generate_notes_land_area(source="test", reference_total=9_596_960.0)
    assert "9,596,960" in notes


# ---------------------------------------------------------------------------
# build_tags
# ---------------------------------------------------------------------------

def test_build_tags_returns_five_tags():
    tags = build_tags(
        category="development",
        indicator_id="gdp_pc_ppp",
        entity_slug="india",
        entity_type="major",
        era="current",
    )
    assert len(tags) == 5


def test_build_tags_prefixes():
    tags = build_tags(
        category="development",
        indicator_id="gdp_pc_ppp",
        entity_slug="india",
        entity_type="major",
        era="current",
    )
    assert "category::development" in tags
    assert "indicator::gdp_pc_ppp" in tags
    assert "entity::india" in tags
    assert "entity_type::major" in tags
    assert "era::current" in tags


def test_build_tags_historical_era():
    tags = build_tags(
        category="finance",
        indicator_id="gini",
        entity_slug="brazil",
        entity_type="major",
        era="2000",
    )
    assert "era::2000" in tags


def test_build_tags_returns_list():
    tags = build_tags("cat", "ind", "slug", "type", "era")
    assert isinstance(tags, list)
    assert all(isinstance(t, str) for t in tags)
