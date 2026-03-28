# Knowledge Base

Calibration training system for building base-rate knowledge of socioeconomic, financial, and development indicators. The primary interface is a TUI-based spaced repetition app where users estimate 95% confidence intervals or point predictions for real-world quantities — building calibrated order-of-magnitude intuitions relevant to GJOpen/Metaculus-style forecasting.

An [Anki with Uncertainty](https://github.com/Sage-Future/anki-with-uncertainty) export pipeline is maintained for sharing and backup.

## Decks

Eight decks spanning ~50 indicators across 47 countries and 50 major cities.

### Global Development

13 indicators across 47 entities (7 world regions, 15 major economies, 25 development-relevant countries) and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Development | GDP per capita (PPP), poverty headcount, Gini coefficient, trade/GDP |
| Health | Life expectancy, under-5 mortality, maternal mortality, fertility rate |
| Energy | CO2 per capita, renewable electricity share, energy intensity |
| Geography | Population, land area |

### Technology Adoption

6 indicators across 47 entities and 4 time periods (1990, 2000, 2010, current).

| Indicator | Unit |
|-----------|------|
| Internet users | % of population |
| Mobile cellular subscriptions | per 100 people |
| Fixed broadband subscriptions | per 100 people |
| R&D expenditure | % of GDP |
| High-technology exports | % of manufactured exports |
| Electricity access | % of population |

### Conflict & Security

7 indicators across 47 entities and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Military | Military expenditure (% of GDP), military expenditure (USD), armed forces personnel, arms imports |
| Security | Intentional homicides, refugees by country of origin, refugees by country of asylum |

### Finance & Markets

8 indicators across 47 entities and 3 time periods (~1960, ~1990, current).

| Category | Indicators |
|----------|-----------|
| Macro | Inflation (CPI), current account balance, total reserves including gold, real interest rate |
| Financial System | Market capitalization, stocks traded, domestic credit to private sector, personal remittances received |

### Education

4 indicators across 47 entities and 2 time periods (~1990, current).

| Indicator | Unit |
|-----------|------|
| Adult literacy rate | % of people ages 15+ |
| Secondary school enrollment | % gross |
| Tertiary school enrollment | % gross |
| Government education expenditure | % of GDP |

### Governance

6 Worldwide Governance Indicators across 40 country entities and 2 time periods (~2000, current). No regional aggregates.

| Indicator | WB Code |
|-----------|---------|
| Government effectiveness | GE.EST |
| Control of corruption | CC.EST |
| Rule of law | RL.EST |
| Regulatory quality | RQ.EST |
| Voice and accountability | VA.EST |
| Political stability | PV.EST |

All indicators use a standardized index scale (-2.5 to +2.5).

### Urban Areas

6 indicators for 50 major cities (by 2025 population) plus income-group aggregates, across 5 time periods (1990, 2000, 2010, 2020, 2025).

| Category | Indicators |
|----------|-----------|
| Demographics | Population |
| Emissions | CO2 per capita, PM2.5 concentration |
| Socioeconomic | Life expectancy, HDI |
| Urban Form | Built-up area per capita |

**Data source:** GHS Urban Centre Database (R2024A).

### Descriptive Statistics

Cross-cutting deck with distribution summary cards (mean, median, SD, min, max with entities) for each indicator across all source decks. Uses Enhanced Cloze note type.

---

**Data sources:** World Bank WDI (API) for the four thematic decks, GHS-UCDB for urban areas. Each card includes reference-class context (world average + regional average) to support Fermi-style reasoning.

## SRS Review System

The primary interface is a Textual TUI with score-driven spaced repetition scheduling.

- **Scoring:** Answer-normalized log-likelihood. The user's interval is treated as an implied 95% CI; the score `S = -z²/2 - ln(CoV)` is transformed via logistic to [0,1]. No indicator standard deviation needed — scoring depends only on the interval bounds and true answer. Point predictions use discrete thresholds.
- **Scheduling:** Simplified FSRS model — good scores lower the desired retention target, producing longer review intervals. All cards use FSRS directly (no learning/review state machine). New cards are presented in random order for interleaved practice.
- **Statistics:** Brier score, calibration rate, score distribution histograms, point prediction hit rates — viewable per deck or per indicator.

## Architecture

Three-stage pipeline: `fetch` → CSVs → `srs-import` → SQLite → `review` TUI

```
fetch-data / fetch-urban-data / fetch-desc-stats → data/{deck}/*.csv
    ↓                                                    ↓
srs-import → data/srs.db → review TUI            build-deck → .apkg
```

The CSV intermediary makes manual corrections straightforward — edit a CSV, re-run `srs-import` or `build-deck`.

## Setup

```bash
uv sync                              # install dependencies

# Fetch data
uv run fetch-data development        # World Bank → data/development/*.csv
uv run fetch-data tech_adoption
uv run fetch-data conflict_security
uv run fetch-data finance
uv run fetch-data education
uv run fetch-data governance
uv run fetch-urban-data              # GHS-UCDB → data/urban_areas/*.csv
uv run fetch-desc-stats              # compute stats → data/descriptive_stats/*.csv

# SRS review system
uv run srs-import --all              # import all decks → data/srs.db
uv run review                        # launch TUI review session
uv run review --stats                # stats screen only

# Anki export (sharing/backup)
uv run build-deck development        # → knowledge_base.apkg
uv run build-deck tech_adoption      # → knowledge_base_tech_adoption.apkg

uv run pytest                        # 218 tests
```

Anki export requires the [Anki with Uncertainty](https://www.quantifiedintuitions.org/anki-with-uncertainty) add-on (code `694813595`).

## Tag Schema

Cards are tagged for filtering:

- `category::development`, `category::health`, `category::energy`, `category::geography`, `category::technology`, `category::military`, `category::security`, `category::macro`, `category::financial_system`, `category::education`, `category::governance`
- `indicator::gdp_pc_ppp`, `indicator::internet_users`, etc.
- `entity::india`, `entity::sub_saharan_africa`, etc.
- `entity_type::region`, `entity_type::major`, `entity_type::long_tail`
- `era::1960`, `era::1990`, `era::2000`, `era::2010`, `era::current`
- `source_deck::development`, etc. (descriptive stats cards only)

## Project Structure

```
src/knowledge_base/
    config.py            # DECKS registry, entity lists, indicator metadata
    card_gen.py          # Question/answer/tag generation (shared by build_deck + srs)
    wb_api.py            # World Bank API client
    ghsl.py              # GHS-UCDB GeoPackage reader
    fetch_data.py        # World Bank → data/<deck>/*.csv
    fetch_urban_data.py  # GHS-UCDB → data/urban_areas/*.csv
    fetch_desc_stats.py  # Compute descriptive statistics → data/descriptive_stats/*.csv
    desc_stats.py        # Statistics computation helper
    build_deck.py        # CSV → .apkg (Anki export)
    srs/
        scoring.py       # Answer-normalized log-likelihood interval scoring, point prediction scoring
        scheduler.py     # Simplified FSRS scheduling (DSR model)
        db.py            # SQLite schema, CRUD, migrations
        importer.py      # CSV → SQLite card import
        stats.py         # Calibration metrics and score distributions
        tui.py           # Textual TUI for review sessions
data/
    development/         # Curated CSVs (gitignored, regenerated by fetch commands)
    tech_adoption/
    conflict_security/
    finance/
    education/
    governance/
    urban_areas/
    descriptive_stats/
    srs.db               # Personal review state (gitignored)
tests/                   # 218 tests
```
