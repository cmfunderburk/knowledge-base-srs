# Year-on-Year Percentage Change (QuantEcon 17.5.2)

> The textbook exercise pulls live data via `yfinance`. To make the exercise deterministic for testing, the network call is factored out: you receive a price DataFrame as input.

You are given a DataFrame `prices` of daily closing prices spanning many years:

- The index is a `DatetimeIndex` of trading days, sorted ascending.
- Columns are index symbols (e.g. `^GSPC`, `^IXIC`, `^DJI`, `^N225`).
- Values are closing prices (floats), with `NaN` allowed for days before an index existed.

Write a function `yearly_returns(prices)` that returns a `pandas.DataFrame` of year-on-year fractional returns:

- The index is the calendar year (integer).
- The columns match `prices.columns`.
- For each year and each ticker, the value is

$$
\text{return}_{y, t} = \frac{p_{y,t}^{\text{last}} - p_{y,t}^{\text{first}}}{p_{y,t}^{\text{first}}}
$$

where $p_{y,t}^{\text{first}}$ is the first non-NaN closing price for ticker $t$ in year $y$, and $p_{y,t}^{\text{last}}$ is the last.

Years in which a ticker has no observations should give `NaN` for that ticker.

Hint: `prices.groupby(prices.index.year)[col].first()` / `.last()` is the textbook approach.
