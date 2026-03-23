# Anki with Uncertainty — OWID Knowledge Base Deck Design

## Overview

A calibration-training Anki deck of numerical estimation questions using the [Anki with Uncertainty](https://github.com/Sage-Future/anki-with-uncertainty) add-on (code `694813595`). Cards cover OWID-style development, health, energy, and geography indicators across ~47 entities and 3 time periods. The goal is calibrated order-of-magnitude intuitions, not exact recall.

## Note Type

Reuses the existing "Interval" note type (model ID `1677887272395`) from the add-on's example deck. Four fields:

| # | Field | Content |
|---|-------|---------|
| 0 | `Front` | Natural language question with explicit units |
| 1 | `Answer (must be a number)` | Numerical answer |
| 2 | `Notes` | Source attribution + world avg + regional avg |
| 3 | `Desired accuracy multiplier` | Left blank (default = 1) |

The card templates (qfmt/afmt) with all scoring JavaScript are copied verbatim from the example deck.

## Entity Selection (~47 entities)

### Regions (7)
World, Sub-Saharan Africa, South Asia, East Asia & Pacific, Latin America & Caribbean, Middle East & North Africa, Europe & Central Asia

### Major Economies (~15)
USA, China, India, Japan, Germany, UK, France, Brazil, Indonesia, Russia, Mexico, South Korea, Turkey, Nigeria, Saudi Arabia

### Long-Tail Sample (~25)
Bangladesh, Vietnam, Ethiopia, Kenya, Ghana, Tanzania, Egypt, Pakistan, Philippines, Thailand, Colombia, Argentina, Chile, South Africa, Poland, Ukraine, Iran, Iraq, Malaysia, Myanmar, DR Congo, Mozambique, Rwanda, Cambodia, Bolivia

Selection criteria: weighted toward countries that appear frequently in development discussions — fast growers (Vietnam, Rwanda, Bangladesh), large-population countries (DR Congo, Pakistan), and middle-income benchmarks (Chile, Colombia, Argentina).

## Indicators (14)

### Development Economics
| Indicator | Unit | Price Basis |
|-----------|------|-------------|
| GDP per capita (PPP) | international $ | 2017 ICP |
| Extreme poverty headcount ratio | % of pop. below $2.15/day | 2017 PPP |
| Gini coefficient | 0–100 scale | — |
| Trade as % of GDP | % | — |

### Health & Demography
| Indicator | Unit |
|-----------|------|
| Life expectancy at birth | years |
| Under-5 mortality rate | deaths per 1,000 live births |
| Maternal mortality ratio | deaths per 100,000 live births |
| Total fertility rate | births per woman |

### Energy & Environment
| Indicator | Unit |
|-----------|------|
| CO2 emissions per capita | tonnes/year |
| Renewable share of electricity | % |
| Energy intensity of GDP | kWh per $ of GDP |

### Geography
| Indicator | Unit |
|-----------|------|
| Population | people |
| Land area | km² |
| Major city populations | people |

## Time Periods

Three eras, chosen to bracket distinct development regimes:

| Era | Target | Acceptable Range | Rationale |
|-----|--------|------------------|-----------|
| Postwar baseline | ~1960 | 1955–1965 | Pre-Green Revolution, early decolonization |
| End of Cold War | ~1990 | 1988–1992 | Berlin Wall, Washington Consensus inflection |
| Current | Most recent available | — | Present-day snapshot |

Use the closest available data year within the acceptable range. Cards are generated only where data exists.

### Data Availability Constraints
- **Poverty & Gini**: sparse before ~1980. Many entities will have only 1990 + current.
- **Renewables & energy intensity**: essentially no 1960 data. Mostly 1990 + current.
- **Land area**: time-invariant. One card per entity, no era dimension.
- **Major city populations**: current only (historical city data is unreliable). Only for entities with cities in the ~top 100 globally.

## Question Format

Natural language with explicit units and price basis where applicable:

```
What was India's GDP per capita (PPP) in 1990, in 2017 international dollars?
```

```
What was the under-5 mortality rate in Sub-Saharan Africa in 1960, in deaths per 1,000 live births?
```

```
What is the population of Ethiopia as of 2023?
```

## Notes Field Format

Source attribution + reference class comparisons:

**For country-level cards:**
```
OWID / World Bank WDI, retrieved 2026-03. World avg: $15,000. South Asia regional avg: $7,200.
```

**For region-level cards:**
```
OWID / World Bank WDI, retrieved 2026-03. World avg: $15,000.
```

## Deck & Tag Structure

**Single flat deck:** `Knowledge Base`

Interleaved scheduling across categories — no subdecks. All filtering via tags.

**Tag schema:**
- `category::development`, `category::health`, `category::energy`, `category::geography`
- `indicator::gdp_pc_ppp`, `indicator::life_expectancy`, `indicator::under5_mortality`, etc.
- `entity::india`, `entity::sub_saharan_africa`, etc.
- `entity_type::region`, `entity_type::major`, `entity_type::long_tail`
- `era::1960`, `era::1990`, `era::current`

## Card Count Estimate

~47 entities × 14 indicators × 3 eras = ~1,974 theoretical maximum.

After data availability constraints: **~1,200–1,500 cards.**

This is a living deck designed to grow as the knowledge base expands.

## Technical Implementation

- **Generation tool:** genanki (Python), managed with uv
- **Data sources:** OWID / World Bank WDI (primary), supplemented as needed
- **Model ID:** Reuse `1677887272395` from the add-on example deck so the note type merges cleanly
- **Card templates:** Copied verbatim from the example deck (contains scoring JS)
- **Output:** `.apkg` file
