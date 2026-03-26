from pathlib import Path

import pytest

from knowledge_base.ghsl import fetch_indicator

FIXTURE = Path(__file__).parent / "fixtures" / "sample_urban.gpkg"


def test_fetch_population():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="GHSL",
        column_prefix="GH_POP_TOT",
        uc_ids=[100, 200, 300],
        years=[2020, 2025],
    )
    assert len(results) == 6
    r100_2020 = [r for r in results if r["uc_id"] == 100 and r["year"] == 2020]
    assert len(r100_2020) == 1
    assert r100_2020[0]["value"] == pytest.approx(10_000_000)


def test_fetch_filters_by_uc_ids():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="GHSL",
        column_prefix="GH_POP_TOT",
        uc_ids=[100],
        years=[2020],
    )
    assert len(results) == 1
    assert results[0]["uc_id"] == 100


def test_fetch_skips_null_values():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="SOCIOECONOMIC",
        column_prefix="SC_SEC_LET",
        uc_ids=[100, 200, 300],
        years=[2020],
    )
    assert len(results) == 2
    uc_ids = {r["uc_id"] for r in results}
    assert 300 not in uc_ids


def test_fetch_nonexistent_year_returns_empty():
    results = fetch_indicator(
        gpkg_path=FIXTURE,
        table_name="EMISSIONS",
        column_prefix="EM_CO2_PEC",
        uc_ids=[100],
        years=[1990],
    )
    assert results == []
