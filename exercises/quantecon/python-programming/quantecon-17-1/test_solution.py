import sys

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
    # Three tickers, five trading days. Picked so the answers are easy:
    #   AAA: 100 → 110  → +10%
    #   BBB: 50  → 25   → -50%
    #   CCC: 200 → 200  →  0%
    dates = pd.date_range("2021-01-04", periods=5, freq="B")
    return pd.DataFrame(
        {
            "AAA": [100.0, 105.0, 102.0, 108.0, 110.0],
            "BBB": [50.0, 60.0, 40.0, 30.0, 25.0],
            "CCC": [200.0, 195.0, 210.0, 198.0, 200.0],
        },
        index=dates,
    )


def test_percentage_change_exists(sub):
    assert hasattr(sub, "percentage_change")
    assert callable(sub.percentage_change)


def test_returns_series(sub, prices):
    out = sub.percentage_change(prices)
    assert isinstance(out, pd.Series), f"expected pandas.Series, got {type(out).__name__}"


def test_index_matches_tickers(sub, prices):
    out = sub.percentage_change(prices)
    assert set(out.index) == {"AAA", "BBB", "CCC"}


def test_values(sub, prices):
    out = sub.percentage_change(prices)
    assert out.loc["AAA"] == pytest.approx(10.0)
    assert out.loc["BBB"] == pytest.approx(-50.0)
    assert out.loc["CCC"] == pytest.approx(0.0)


def test_single_ticker(sub):
    prices = pd.DataFrame({"X": [10.0, 20.0]})
    out = sub.percentage_change(prices)
    assert out.loc["X"] == pytest.approx(100.0)


def test_long_series(sub):
    # 252 trading days; only first and last matter.
    n = 252
    prices = pd.DataFrame(
        {
            "AAA": [100.0 + 0.1 * i for i in range(n)],  # ends at 100 + 25.1 = 125.1
        }
    )
    out = sub.percentage_change(prices)
    expected = (prices["AAA"].iloc[-1] - 100.0) / 100.0 * 100
    assert out.loc["AAA"] == pytest.approx(expected)
