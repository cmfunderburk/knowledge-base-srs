import pandas as pd


def percentage_change(prices: pd.DataFrame) -> pd.Series:
    p1 = prices.iloc[0]
    p2 = prices.iloc[-1]
    return (p2 - p1) / p1 * 100
