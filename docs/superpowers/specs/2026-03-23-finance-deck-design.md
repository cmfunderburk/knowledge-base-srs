# Knowledge Base::Finance & Markets — Deck Design

## Overview

A fourth Anki with Uncertainty deck covering macroeconomic and financial system indicators. Uses the same 47 entities and 3-era structure as the development deck. All data sourced from World Bank WDI — no new API integrations required. A future phase will add US-only financial market indicators from FRED.

## Deck Registry Entry

```python
"finance": {
    "name": "Knowledge Base::Finance & Markets",
    "deck_id": 2026032303,
    "output": "knowledge_base_finance.apkg",
    "data_dir": "data/finance",
    "era_ranges": {
        "1960": (1955, 1965, 1960),
        "1990": (1988, 1992, 1990),
        "current": (2020, 2026, 2026),
    },
    "indicators": [ ... ],  # 8 indicators below
}
```

Same era_ranges as the development deck. Same `ENTITIES` (47 shared).

## Entity Selection

Same 47 entities as the other decks (7 regions, 15 major economies, 25 long-tail countries). Cards generated only where data exists.

## Era Ranges

| Era | Target | Acceptable Range | Rationale |
|-----|--------|------------------|-----------|
| 1960 | 1960 | 1955–1965 | Bretton Woods era baseline |
| 1990 | 1990 | 1988–1992 | Post-Cold War financial globalization |
| Current | Most recent | 2020–2026 | Present-day snapshot |

## Indicators (8)

| id | name | category | unit_label | wb_code | decimals | scale_factor | has_regional_aggregates |
|----|------|----------|------------|---------|----------|-------------|------------------------|
| inflation | Inflation (CPI) | macro | annual % | FP.CPI.TOTL.ZG | 1 | 1 | True |
| current_account | Current account balance | macro | % of GDP | BN.CAB.XOKA.GD.ZS | 1 | 1 | False |
| reserves | Total reserves including gold | macro | billions of current US$ | FI.RES.TOTL.CD | 1 | 1000000000 | False |
| real_interest_rate | Real interest rate | macro | % | FR.INR.RINR | 1 | 1 | False |
| market_cap | Market capitalization | financial_system | % of GDP | CM.MKT.LCAP.GD.ZS | 1 | 1 | True |
| stocks_traded | Stocks traded | financial_system | % of GDP | CM.MKT.TRAD.GD.ZS | 1 | 1 | True |
| domestic_credit | Domestic credit to private sector | financial_system | % of GDP | FS.AST.PRVT.GD.ZS | 1 | 1 | True |
| remittances | Personal remittances received | financial_system | billions of current US$ | BX.TRF.PWKR.CD.DT | 1 | 1000000000 | True |

All sourced from World Bank WDI. No new data sources required. All indicators use `unit_prefix: ""`, `time_invariant: False`, `current_only: False`.

### Data Availability Notes

- **Inflation (CPI)**: Excellent coverage from 1960. All 7 regional aggregates. China starts ~1987. Wide variation (0.2%–33%+).
- **Current account balance**: Good from 1975. No 1960 era for most countries. No regional aggregates. Interesting surplus/deficit variation.
- **Total reserves including gold**: Good from 1960. No regional aggregates. Absolute values scaled to billions. China $3.5T vs Nigeria $39B.
- **Real interest rate**: Available from 1960 for some countries. Germany missing entirely. No regional aggregates. Some countries have gaps.
- **Market capitalization**: Good from 1975. 6 of 7 regions have data. USA 216% vs Nigeria 22%. No 1960 era data.
- **Stocks traded**: Good from 1975. All 7 regions. Massive variation (Nigeria 0.6% vs China 186%).
- **Domestic credit to private sector**: Good from 1960 using corrected code `FS.AST.PRVT.GD.ZS`. Most regions have data, though WLD only from 2023.
- **Remittances**: Good from 1970. All 7 regions. Absolute values scaled to billions. India $138B dominates.

## Question Format

Same natural language format as other decks:

```
What was India's Inflation (CPI) in 1990, annual %?
```

```
What is China's Total reserves including gold as of 2024, billions of current US$?
```

```
What was Brazil's Current account balance in 1990, % of GDP?
```

## Notes Field

Same format: source + world avg + regional avg (where available), scaled to match the indicator:

```
Source: World Bank WDI | World avg: 3.5, regional avg: 6.2
```

For indicators without regional aggregates (current_account, reserves, real_interest_rate): notes show source + world average (where available), but no regional average. Reference averages use the same `scale_factor` and `decimals` as the answer.

## Tag Schema

- `category::macro`, `category::financial_system`
- `indicator::inflation`, `indicator::market_cap`, etc.
- `entity::india`, `entity_type::major`, etc.
- `era::1960`, `era::1990`, `era::current`

## Card Count Estimate

40 countries × 8 indicators × 3 eras = 960 theoretical max. (7 region entities are used for reference averages only, not card generation.)

After data gaps (current account and real interest rate missing 1960 for many countries, market cap and stocks traded start ~1975, some developing country gaps): **~550–700 cards.**

## Implementation Scope

No code changes required beyond configuration:

1. Add `DECKS["finance"]` entry in `config.py` with 8 indicators
2. Create `data/finance/.gitkeep`
3. Update CLAUDE.md (add `finance` to available deck keys)
4. Update README.md (add Finance & Markets deck section)

No changes to `wb_api.py`, `fetch_data.py`, or `build_deck.py`.

## Technical Details

- **Data source**: World Bank WDI API only (existing `wb_api.py` client)
- **GUID stability**: Same approach — Front field uniqueness ensures stable GUIDs across deck rebuilds
- **Answer rounding**: Per-indicator `decimals` field, applied after `scale_factor` division
- **Deck ID**: `2026032303` (distinct from development `2026032300`, tech adoption `2026032301`, conflict & security `2026032302`)

## Future Extension: FRED Phase

A future phase will add ~7 US-only financial market indicators from FRED (Federal Reserve Economic Data). This is deferred pending API key setup. The planned additions:

| Indicator | FRED Series | Coverage |
|-----------|------------|----------|
| 10-Year Treasury yield | DGS10 | 1962–present |
| Federal Funds rate | FEDFUNDS | 1954–present |
| US unemployment rate | UNRATE | 1948–present |
| US debt-to-GDP | GFDEGDQ188S | 1966–present |
| Gold price (USD/oz) | GOLDAMGBD228NLBM | 1968–present |
| Baa corporate bond yield | BAA | 1919–present |
| Median home sale price | MSPUS | 1963–present |

The FRED phase would require:
- A `fred_api.py` client (or bundled CSV approach using curated data)
- A `FRED_API_KEY` environment variable (free registration)
- FRED indicators would use a 4-era structure (1960/1990/2010/current) for higher temporal resolution
- An `entity_override` flag for global indicators like gold (question omits entity name)
- Mixed WB + FRED indicators within the same deck config

This extension does not affect the current WB-only implementation.
