from knowledge_base.config import DECKS
from knowledge_base.fetch_data import (
    select_best_year_for_era,
    build_indicator_dataframe,
    EXPECTED_COLUMNS,
)

DEV_ERA_RANGES = DECKS["development"]["era_ranges"]


def test_select_best_year_for_era_prefers_target():
    records = [
        {"country_code": "IND", "year": 1958, "value": 100},
        {"country_code": "IND", "year": 1960, "value": 110},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best["year"] == 1960


def test_select_best_year_for_era_picks_closest():
    records = [
        {"country_code": "IND", "year": 1956, "value": 100},
        {"country_code": "IND", "year": 1963, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best["year"] == 1963


def test_select_best_year_for_era_returns_none_outside_range():
    records = [
        {"country_code": "IND", "year": 1950, "value": 100},
    ]
    best = select_best_year_for_era(records, "IND", "1960", DEV_ERA_RANGES)
    assert best is None


def test_select_best_year_for_current_era():
    records = [
        {"country_code": "IND", "year": 2020, "value": 100},
        {"country_code": "IND", "year": 2022, "value": 110},
        {"country_code": "IND", "year": 2023, "value": 120},
    ]
    best = select_best_year_for_era(records, "IND", "current", DEV_ERA_RANGES)
    assert best["year"] == 2023


def test_build_indicator_dataframe_columns():
    rows = [{
        "entity": "India",
        "entity_type": "major",
        "region": "South Asia",
        "era": "1990",
        "year": 1990,
        "value": 1806.0,
        "source": "World Bank WDI",
    }]
    df = build_indicator_dataframe(rows)
    assert set(df.columns) == set(EXPECTED_COLUMNS)
