# Knowledge Base

Programmatic generation of [Anki with Uncertainty](https://github.com/Sage-Future/anki-with-uncertainty) flashcard decks for calibration training on real-world numerical quantities. Instead of recalling exact answers, users enter confidence intervals — building calibrated order-of-magnitude intuitions.

## Current Decks

### Global Development Indicators

**1,082 cards** covering 14 indicators across 47 entities (7 world regions, 15 major economies, 25 development-relevant countries) and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Development | GDP per capita (PPP), poverty headcount, Gini coefficient, trade/GDP |
| Health | Life expectancy, under-5 mortality, maternal mortality, fertility rate |
| Energy | CO2 per capita, renewable electricity share, energy intensity |
| Geography | Population, land area, major city populations |

**Data sources:** World Bank WDI (API), UN World Urbanization Prospects 2025.

**Time periods:** Post-WWII baseline (~1960), end of Cold War (~1990), and current — chosen to bracket distinct development regimes and build intuitions about rates of change.

### Technology Adoption

**738 cards** covering 6 indicators across the same 47 entities and 4 time periods (1990, 2000, 2010, current).

| Indicator | Unit |
|-----------|------|
| Internet users | % of population |
| Mobile cellular subscriptions | per 100 people |
| Fixed broadband subscriptions | per 100 people |
| R&D expenditure | % of GDP |
| High-technology exports | % of manufactured exports |
| Electricity access | % of population |

**Data source:** World Bank WDI (API).

**Time periods:** Decade intervals from 1990 to present, capturing the internet boom and mobile revolution.

---

Each card includes reference-class context in the notes field (world average + regional average) to support Fermi-style reasoning.

## Architecture

Two-stage pipeline with a curated CSV intermediary, supporting multiple decks via a `DECKS` registry in `config.py`:

```
fetch-data <deck>  →  data/<deck>/*.csv  →  build-deck <deck>  →  *.apkg
(World Bank API)      (one per indicator)    (genanki)            (import to Anki)
```

- **Stage 1** (`uv run fetch-data <deck>`): Downloads from the World Bank API, selects the best data point per entity/era, writes one CSV per indicator.
- **Stage 2** (`uv run build-deck <deck>`): Reads CSVs, generates question text with explicit units, computes reference-class averages, assigns tags, and produces the `.apkg` file.

The CSV intermediary makes manual corrections and additions straightforward — edit a CSV, re-run `build-deck`.

## Setup

```bash
uv sync                          # install dependencies
uv run fetch-data development    # download data → data/development/*.csv
uv run fetch-data tech_adoption  # download data → data/tech_adoption/*.csv
uv run build-deck development    # generate knowledge_base.apkg
uv run build-deck tech_adoption  # generate knowledge_base_tech_adoption.apkg
uv run pytest                    # run tests (25 tests)
```

Requires the [Anki with Uncertainty](https://www.quantifiedintuitions.org/anki-with-uncertainty) add-on (code `694813595`) installed in Anki.

## Tag Schema

All cards in each deck use interleaved scheduling. Filtering via tags:

- `category::development`, `category::health`, `category::energy`, `category::geography`, `category::technology`
- `indicator::gdp_pc_ppp`, `indicator::internet_users`, etc.
- `entity::india`, `entity::sub_saharan_africa`, etc.
- `entity_type::region`, `entity_type::major`, `entity_type::long_tail`
- `era::1960`, `era::1990`, `era::2000`, `era::2010`, `era::current`

## Project Structure

```
src/knowledge_base/
    config.py        # DECKS registry, entity lists, indicator metadata, WB API codes
    wb_api.py        # World Bank API client
    fetch_data.py    # Stage 1: download & clean → data/<deck>/*.csv
    build_deck.py    # Stage 2: data/<deck>/*.csv → .apkg
data/
    development/     # Curated CSVs for development deck (gitignored)
    tech_adoption/   # Curated CSVs for tech adoption deck (gitignored)
resources/           # Bundled data (UN WUP cities CSV, example deck)
tests/               # 25 tests
docs/superpowers/
    specs/           # Design specs
    plans/           # Implementation plans
```
