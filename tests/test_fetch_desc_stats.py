import polars as pl
import pytest
from pathlib import Path
from knowledge_base.fetch_desc_stats import (
    compute_wb_indicator_stats,
    STATS_COLUMNS,
    build_stats_dataframe,
)


def test_compute_wb_indicator_stats_from_records():
    """Given raw WB API records, compute stats for one indicator."""
    records = [
        {"country_code": "USA", "year": 2023, "value": 75000.0},
        {"country_code": "IND", "year": 2023, "value": 9000.0},
        {"country_code": "NGA", "year": 2022, "value": 5000.0},
        {"country_code": "CHN", "year": 2023, "value": 23000.0},
    ]
    country_names = {
        "USA": "United States",
        "IND": "India",
        "NGA": "Nigeria",
        "CHN": "China",
    }
    stats = compute_wb_indicator_stats(records, country_names)
    assert stats["n"] == 4
    assert stats["mean"] == pytest.approx(28000.0)
    assert stats["min_value"] == pytest.approx(5000.0)
    assert stats["min_entity"] == "Nigeria"
    assert stats["max_value"] == pytest.approx(75000.0)
    assert stats["max_entity"] == "United States"
    assert isinstance(stats["year"], int)


def test_compute_wb_indicator_stats_picks_most_recent_per_country():
    """When a country has multiple years, pick the most recent."""
    records = [
        {"country_code": "USA", "year": 2020, "value": 60000.0},
        {"country_code": "USA", "year": 2023, "value": 75000.0},
        {"country_code": "IND", "year": 2022, "value": 9000.0},
    ]
    country_names = {"USA": "United States", "IND": "India"}
    stats = compute_wb_indicator_stats(records, country_names)
    assert stats["n"] == 2
    assert stats["max_value"] == pytest.approx(75000.0)


def test_build_stats_dataframe():
    row = {
        "indicator_id": "gdp_pc_ppp",
        "indicator_name": "GDP per capita (PPP)",
        "category": "development",
        "source_deck": "development",
        "unit_label": "in 2021 international dollars",
        "unit_prefix": "$",
        "decimals": 0,
        "scale_factor": 1,
        "year": 2023,
        "n": 190,
        "mean": 18000.0,
        "median": 13000.0,
        "std": 22000.0,
        "min_value": 800.0,
        "min_entity": "Burundi",
        "max_value": 140000.0,
        "max_entity": "Luxembourg",
    }
    df = build_stats_dataframe(row)
    assert set(df.columns) == set(STATS_COLUMNS)
    assert len(df) == 1
