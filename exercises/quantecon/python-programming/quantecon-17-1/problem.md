# Percentage Price Change (QuantEcon 17.5.1)

> The textbook exercise pulls live data from Yahoo Finance via `yfinance`. To make the exercise deterministic for testing, the network call is factored out: you receive a price DataFrame as input.

You are given a DataFrame `prices` of daily closing prices:

- Rows are trading days, indexed in chronological order (oldest first, most recent last).
- Columns are ticker symbols (e.g. `INTC`, `MSFT`, `IBM`, `AAPL`, ...).
- Values are closing prices (floats).

Write a function `percentage_change(prices)` that returns a `pandas.Series` giving, for each ticker, the percentage change from the first row's price to the last row's price:

$$
\text{pct}_t = \frac{p_t^{\text{last}} - p_t^{\text{first}}}{p_t^{\text{first}}} \times 100
$$

The returned Series is indexed by ticker (the columns of `prices`).

You may use any pandas idiom. The two natural approaches from the textbook are:

1. Extract `prices.iloc[0]` and `prices.iloc[-1]` and compute the change directly.
2. Use `prices.pct_change(periods=len(prices)-1).iloc[-1] * 100`.

Restrict your imports to `pandas`.
