import pandas as pd


def yearly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    for col in prices.columns:
        p1 = prices.groupby(prices.index.year)[col].first()
        p2 = prices.groupby(prices.index.year)[col].last()
        out[col] = (p2 - p1) / p1
    return out
