import math
import sys

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


@pytest.fixture
def prices():
    # Two tickers, three years of monthly data — designed so returns are easy:
    #   AAA: starts each year at 100, ends at 110/121/132.1 → +10% each year
    #   BBB: starts at 50/55/60 and ends at 60/55/50 → +20%, 0%, -16.67%
    rows = []
    aaa_starts = {2019: 100.0, 2020: 100.0, 2021: 100.0}
    aaa_ends = {2019: 110.0, 2020: 121.0, 2021: 132.1}
    bbb_first = {2019: 50.0, 2020: 55.0, 2021: 60.0}
    bbb_last = {2019: 60.0, 2020: 55.0, 2021: 50.0}
    for year in (2019, 2020, 2021):
        dates = pd.date_range(f"{year}-01-15", f"{year}-12-15", freq="MS")
        # Linear interp between first and last
        n = len(dates)
        for i, d in enumerate(dates):
            a = aaa_starts[year] + (aaa_ends[year] - aaa_starts[year]) * i / (n - 1)
            b = bbb_first[year] + (bbb_last[year] - bbb_first[year]) * i / (n - 1)
            rows.append((d, a, b))
    df = pd.DataFrame(rows, columns=["date", "AAA", "BBB"]).set_index("date").sort_index()
    return df


def test_yearly_returns_exists(sub):
    assert hasattr(sub, "yearly_returns")
    assert callable(sub.yearly_returns)


def test_returns_dataframe(sub, prices):
    out = sub.yearly_returns(prices)
    assert isinstance(out, pd.DataFrame)


def test_columns_match(sub, prices):
    out = sub.yearly_returns(prices)
    assert list(out.columns) == ["AAA", "BBB"]


def test_index_is_years(sub, prices):
    out = sub.yearly_returns(prices)
    assert set(out.index) == {2019, 2020, 2021}


def test_values_aaa(sub, prices):
    out = sub.yearly_returns(prices)
    assert out.loc[2019, "AAA"] == pytest.approx(0.10)
    assert out.loc[2020, "AAA"] == pytest.approx(0.21)
    assert out.loc[2021, "AAA"] == pytest.approx(0.321)


def test_values_bbb(sub, prices):
    out = sub.yearly_returns(prices)
    assert out.loc[2019, "BBB"] == pytest.approx(0.20)
    assert out.loc[2020, "BBB"] == pytest.approx(0.0)
    assert out.loc[2021, "BBB"] == pytest.approx(-10.0 / 60.0)


def test_nan_for_missing_ticker():
    # If a ticker has no data in a year, return NaN for that year.
    sys.modules.pop("submission", None)
    import submission as s
    sys.modules.pop("submission", None)

    dates = list(pd.date_range("2019-01-15", "2019-12-15", freq="MS")) + list(
        pd.date_range("2020-01-15", "2020-12-15", freq="MS")
    )
    df = pd.DataFrame(
        {
            "X": [100.0 + i for i in range(len(dates))],
            "Y": [np.nan] * 12 + [50.0 + i for i in range(len(dates) - 12)],
        },
        index=dates,
    )
    out = s.yearly_returns(df)
    assert math.isnan(out.loc[2019, "Y"]), "year with all NaN should produce NaN"
    assert not math.isnan(out.loc[2020, "Y"])
