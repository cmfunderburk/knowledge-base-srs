import polars as pl
import pytest
from pathlib import Path
from knowledge_base.build_deck import (
    generate_question,
    generate_notes,
    generate_notes_city,
    generate_notes_land_area,
    compute_reference_averages,
    build_tags,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_generate_question_with_units():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=2022,
        unit_label="in 2021 international dollars",
        era="current",
    )
    assert q == "What is India's GDP per capita (PPP) as of 2022, in 2021 international dollars?"


def test_generate_question_historical():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=1990,
        unit_label="in 2021 international dollars",
        era="1990",
    )
    assert q == "What was India's GDP per capita (PPP) in 1990, in 2021 international dollars?"


def test_generate_notes_country():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=7200,
        unit_prefix="$",
    )
    assert "World Bank WDI" in notes
    assert "World avg: $17,500" in notes
    assert "regional avg: $7,200" in notes


def test_generate_notes_region():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=None,
        unit_prefix="$",
    )
    assert "regional avg" not in notes
    assert "World avg: $17,500" in notes


def test_build_tags():
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


def test_compute_reference_averages():
    df = pl.read_csv(FIXTURES / "sample_gdp.csv")
    world_avg, region_avgs = compute_reference_averages(df, "current")
    assert world_avg == pytest.approx(17500)
    assert region_avgs["South Asia"] == pytest.approx(7200)


def test_generate_notes_city():
    notes = generate_notes_city(
        source="UN World Urbanization Prospects 2024",
        country_population=1_400_000_000,
    )
    assert "UN World Urbanization Prospects" in notes
    assert "Country population: 1,400,000,000" in notes


def test_generate_notes_land_area():
    notes = generate_notes_land_area(
        source="World Bank WDI",
        reference_total=30_370_000,
    )
    assert "World Bank WDI" in notes
    assert "30,370,000" in notes
