# Education & Governance Decks Design

## Overview

Two new World Bank decks expanding coverage into education and institutional governance — the two largest topical gaps for GJOpen/Metaculus-style forecasting calibration.

Both decks use the existing `fetch-data` → `srs-import` → `review` pipeline with zero new infrastructure.

## Education Deck

**Deck key:** `education`
**deck_id:** `2026032806`
**data_dir:** `data/education`
**Era ranges:** 1990, current

| ID | Name | WB Code | Unit | Decimals | Prefix | Scale | Regional Agg |
|---|---|---|---|---|---|---|---|
| `adult_literacy` | Adult literacy rate | `SE.ADT.LITR.ZS` | % of people ages 15+ | 1 | | 1 | Yes |
| `secondary_enrollment` | Secondary school enrollment | `SE.SEC.ENRR` | % gross | 1 | | 1 | Yes |
| `tertiary_enrollment` | Tertiary school enrollment | `SE.TER.ENRR` | % gross | 1 | | 1 | Yes |
| `education_expenditure` | Government education expenditure | `SE.XPD.TOTL.GD.ZS` | % of GDP | 1 | | 1 | Yes |

**Category:** `education` for all indicators.

**Era range tuples:**
- `"1990": (1988, 1992, 1990)`
- `"current": (2020, 2026, 2026)`

**Estimated cards:** 47 entities × 4 indicators × 2 eras = ~376 max, ~280-320 after data gaps.

**Design notes:**
- All indicators are percentages — no scale_factor needed, no unit_prefix.
- `time_invariant: False`, `current_only: False` for all.
- Literacy data is spottier than enrollment for some long-tail countries; missing data is handled gracefully by the existing fetch pipeline (skips missing entity/era combos).
- 1960 era excluded: education data before 1990 is sparse for many long-tail and MENA countries.

## Governance Deck

**Deck key:** `governance`
**deck_id:** `2026032807`
**data_dir:** `data/governance`
**Era ranges:** 2000, current

| ID | Name | WB Code | Unit | Decimals | Prefix | Scale | Regional Agg |
|---|---|---|---|---|---|---|---|
| `govt_effectiveness` | Government effectiveness | `GE.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |
| `corruption_control` | Control of corruption | `CC.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |
| `rule_of_law` | Rule of law | `RL.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |
| `regulatory_quality` | Regulatory quality | `RQ.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |
| `voice_accountability` | Voice and accountability | `VA.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |
| `political_stability` | Political stability | `PV.EST` | index (-2.5 to +2.5) | 2 | | 1 | No |

**Category:** `governance` for all indicators.

**Era range tuples:**
- `"2000": (1998, 2002, 2000)`
- `"current": (2020, 2026, 2026)`

**Estimated cards:** 40 country entities × 6 indicators × 2 eras = ~480 max, ~400-440 after data gaps. Regional entities (7) are skipped since WGI has no regional aggregates.

**Design notes:**
- WGI data starts 1996 (biannual until 2002, annual after). The 2000 era with range 1998-2002 captures the earliest reliable snapshot.
- All six indicators use the same -2.5 to +2.5 standard normal scale. Values typically cluster between -1.5 and +2.0.
- `has_regional_aggregates: False` for all — WGI is strictly country-level.
- `time_invariant: False`, `current_only: False` for all.

## Descriptive Stats Integration

The `descriptive_stats` deck's `source_decks` list gains two new entries: `"education"` and `"governance"`. This adds ~30 new point-prediction cards (10 indicators × 3 stats each: mean, median, SD).

## Estimated Impact

- **New indicators:** 10 (4 education + 6 governance)
- **New interval cards:** ~700-750
- **New descriptive stats cards:** ~30
- **Total after expansion:** ~50 indicators, ~5,100 cards

## Implementation

Changes are limited to `config.py`:
1. Add `education` entry to `DECKS` with 4 indicators
2. Add `governance` entry to `DECKS` with 6 indicators
3. Add both to `descriptive_stats.source_decks`
4. Create `data/education/.gitkeep` and `data/governance/.gitkeep`

Then run the standard pipeline:
```bash
uv run fetch-data education
uv run fetch-data governance
uv run fetch-desc-stats
uv run srs-import education
uv run srs-import governance
uv run srs-import descriptive_stats
```

## Roadmap: Next Expansion Batch

The following domains are planned for future expansion (not in scope here):

**Labor Markets** — unemployment (`SL.UEM.TOTL.ZS`), labor force participation (`SL.TLF.CACT.ZS`), youth unemployment (`SL.UEM.1524.ZS`), employment by sector shares. All World Bank, eras 1990/current.

**Demographic Structure** — age dependency ratio (`SP.POP.DPND`), urbanization rate (`SP.URB.TOTL.IN.ZS`), net migration, median age. All World Bank, eras 1960/1990/current.
