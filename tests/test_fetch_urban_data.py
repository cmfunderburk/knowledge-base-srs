import polars as pl
import pytest
from pathlib import Path

from knowledge_base.fetch_urban_data import (
    compute_median_aggregates,
    build_urban_indicator_dataframe,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_median_aggregates():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
        {"entity": "CityB", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 20.0, "source": "test"},
        {"entity": "CityC", "entity_type": "city", "region": "Lower Middle", "era": "2020", "year": 2020, "value": 5.0, "source": "test"},
    ]
    aggregates = compute_median_aggregates(rows, "test")
    all_cities = [a for a in aggregates if a["entity"] == "All Cities"]
    assert len(all_cities) == 1
    assert all_cities[0]["value"] == pytest.approx(10.0)
    assert all_cities[0]["entity_type"] == "aggregate"
    assert all_cities[0]["era"] == "2020"
    high = [a for a in aggregates if a["entity"] == "High income"]
    assert len(high) == 1
    assert high[0]["value"] == pytest.approx(15.0)
    lower = [a for a in aggregates if a["entity"] == "Lower Middle"]
    assert len(lower) == 1
    assert lower[0]["value"] == pytest.approx(5.0)


def test_compute_median_aggregates_multiple_eras():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2010", "year": 2010, "value": 8.0, "source": "test"},
    ]
    aggregates = compute_median_aggregates(rows, "test")
    eras = {a["era"] for a in aggregates if a["entity"] == "All Cities"}
    assert eras == {"2020", "2010"}


def test_build_urban_indicator_dataframe():
    rows = [
        {"entity": "CityA", "entity_type": "city", "region": "High income", "era": "2020", "year": 2020, "value": 10.0, "source": "test"},
    ]
    df = build_urban_indicator_dataframe(rows)
    assert len(df) == 1
    assert df.columns == ["entity", "entity_type", "region", "era", "year", "value", "source"]
