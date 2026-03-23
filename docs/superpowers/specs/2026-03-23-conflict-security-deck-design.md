# Knowledge Base::Conflict & Security — Deck Design

## Overview

A third Anki with Uncertainty deck covering military spending, armed forces, arms trade, homicides, and refugee displacement. Uses the same 47 entities as the other decks with the same 3-era structure as the development deck (~1960, ~1990, current). All data sourced from World Bank WDI — no new API integrations required.

## Deck Registry Entry

```python
"conflict_security": {
    "name": "Knowledge Base::Conflict & Security",
    "deck_id": 2026032302,
    "output": "knowledge_base_conflict_security.apkg",
    "data_dir": "data/conflict_security",
    "era_ranges": {
        "1960": (1955, 1965, 1960),
        "1990": (1988, 1992, 1990),
        "current": (2020, 2026, 2026),
    },
    "indicators": [ ... ],  # 7 indicators below
}
```

Same era_ranges as the development deck. Same `ENTITIES` (47 shared).

## Entity Selection

Same 47 entities as the other decks (7 regions, 15 major economies, 25 long-tail countries). The entity list already includes countries with high conflict/security relevance: Iraq, Iran, Ukraine, DR Congo, Myanmar, Colombia, Rwanda, etc. Cards generated only where data exists.

## Era Ranges

| Era | Target | Acceptable Range | Rationale |
|-----|--------|------------------|-----------|
| 1960 | 1960 | 1955–1965 | Cold War arms race baseline |
| 1990 | 1990 | 1988–1992 | End of Cold War, "peace dividend" |
| Current | Most recent | 2020–2026 | Present-day snapshot |

Three eras chosen to bracket Cold War vs. post-Cold War vs. present — the natural periodization for security data.

## Indicators (7)

| id | name | category | unit_label | wb_code | decimals | scale_factor | has_regional_aggregates |
|----|------|----------|------------|---------|----------|-------------|------------------------|
| mil_expenditure_gdp | Military expenditure | military | % of GDP | MS.MIL.XPND.GD.ZS | 1 | 1 | True |
| mil_expenditure_usd | Military expenditure | military | billions of current US$ | MS.MIL.XPND.CD | 1 | 1000000000 | True |
| armed_forces | Armed forces personnel | military | thousands | MS.MIL.TOTL.P1 | 0 | 1000 | True |
| arms_imports | Arms imports | military | millions (constant 1990 US$) | MS.MIL.MPRT.KD | 0 | 1000000 | True |
| homicides | Intentional homicides | security | per 100,000 people | VC.IHR.PSRC.P5 | 1 | 1 | True |
| refugees_origin | Refugees by country of origin | security | thousands | SM.POP.RHCR.EO | 0 | 1000 | True |
| refugees_asylum | Refugees by country of asylum | security | thousands | SM.POP.RHCR.EA | 0 | 1000 | True |

All sourced from World Bank WDI. No new data sources required. All indicators use `unit_prefix: ""`, `time_invariant: False`, `current_only: False`.

### Data Availability Notes

- **Military expenditure (% of GDP)**: Good coverage from 1960 for most countries. China starts ~1989. Great variation (0.5%–9%).
- **Military expenditure (USD)**: Good from 1960. Range from ~$100M to ~$900B. Scaled to billions for usability.
- **Armed forces personnel**: Starts ~1985. No 1960 era data. Data stops ~2020, so "current" era may use 2020 values.
- **Arms imports**: Good from 1960. Range from ~17M to ~4B (constant 1990 US$). Scaled to millions.
- **Intentional homicides**: Starts ~1990. No 1960 era data. Huge variation across countries (0.5 to 20+ per 100k). Regional aggregates only from ~2010.
- **Refugees by country of origin**: Good from 1960. Huge variation — Syria origin ~6.8M, many countries near zero.
- **Refugees by country of asylum**: Good from 1960. Turkey/Germany/Pakistan are major hosts.

## Pipeline Change: `scale_factor`

### Motivation

Indicators with absolute values (military expenditure in USD, armed forces personnel, refugee counts) produce numbers that are impractical to type as confidence intervals. A `scale_factor` field on each indicator allows the pipeline to divide raw API values before storing answers, with the `unit_label` communicating the scale to the user.

### Implementation

- New optional field `scale_factor` (int, default 1) added to every indicator dict.
- `format_answer()` in `build_deck.py` divides the raw value by `scale_factor` before rounding to `decimals`.
- Reference averages in the Notes field must also be scaled. Since `compute_reference_averages()` returns raw floats and does not receive the indicator dict, scaling is applied at the call site — dividing the returned world/regional averages by `scale_factor` before passing them to `generate_notes()`.
- `generate_notes_city()` receives a `country_population` value that comes from the UN CSV, not from the World Bank population indicator. When the `population` indicator has a `scale_factor`, `country_population` in the Notes field must also be divided by the same factor for consistency (the Notes field should read "Country pop: 1,426 million" rather than "Country pop: 1,425,893,000").
- `fetch_data.py` is unchanged — CSVs store raw API values. Scaling happens only at deck-build time.
- Small values may round to 0 after scaling (e.g., a country spending $15M on military would show as 0.0 billions). This is acceptable — such values are near-zero relative to the scale and the interval scoring handles this gracefully.

### Cross-Deck Retroactive Changes

The `scale_factor` field also applies to existing decks where absolute values are unwieldy:

**Development deck:**
- `population`: scale_factor 1,000,000 → unit_label changes to "millions"
- `city_population`: scale_factor 1,000,000 → unit_label changes to "millions (metro area)"

**Note:** Changing `unit_label` changes the question text (Front field), which changes the GUID. Existing cards for `population` and `city_population` will become orphans in Anki and new cards will appear. This GUID reset is acceptable — the usability improvement outweighs losing review history on these cards.

**`city_population` precision:** With `scale_factor: 1,000,000` and `decimals: 0`, a city of 1.2M would display as "1". Consider using `decimals: 1` for city_population after scaling so 1.2M displays as "1.2". (The smallest cities in the bundled CSV are ~1M, so no city would round to 0.)

All other existing indicators: scale_factor 1 (default, no change needed).

## Question Format

Same natural language format as other decks, with explicit units communicating the scale:

```
What was India's Military expenditure in 1990, % of GDP?
```

```
What was the USA's Military expenditure in 2023, billions of current US$?
```

```
What is Colombia's Intentional homicides as of 2022, per 100,000 people?
```

```
What was Turkey's Refugees by country of asylum in 1990, thousands?
```

## Notes Field

Same format: source + world avg + regional avg, scaled to match the indicator:

```
Source: World Bank WDI | World avg: 2.3, regional avg: 1.8
```

```
Source: World Bank WDI | World avg: 348.2, regional avg: 89.5
```

Reference averages use the same `scale_factor` and `decimals` as the answer.

## Tag Schema

- `category::military`, `category::security`
- `indicator::mil_expenditure_gdp`, `indicator::homicides`, etc.
- `entity::india`, `entity_type::major`, etc.
- `era::1960`, `era::1990`, `era::current`

## Card Count Estimate

40 countries × 7 indicators × 3 eras = 840 theoretical max. (7 region entities are used for reference averages only, not card generation.)

After data gaps (armed forces/homicides missing 1960 era entirely, developing country gaps in early eras): **~450–600 cards.**

## Implementation Scope

Two concerns, ordered:

1. **Pipeline change** — Add `scale_factor` to the indicator schema, update `format_answer()` in `build_deck.py`, apply `scale_factor` at the `compute_reference_averages()` and `generate_notes_city()` call sites, apply retroactive scaling to development deck's `population` and `city_population`.

2. **New deck** — Add `DECKS["conflict_security"]` entry in `config.py`, create `data/conflict_security/.gitkeep`, run `fetch-data conflict_security` then `build-deck conflict_security`.

No changes to `wb_api.py` or `fetch_data.py`. No new API clients.

## Technical Details

- **Data source**: World Bank WDI API only (existing `wb_api.py` client)
- **GUID stability**: Same approach — Front field uniqueness ensures stable GUIDs across deck rebuilds
- **Answer rounding**: Per-indicator `decimals` field, applied after `scale_factor` division
- **Deck ID**: `2026032302` (distinct from development `2026032300` and tech adoption `2026032301`)
