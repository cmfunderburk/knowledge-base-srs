# Knowledge Base

A TUI-based spaced repetition system with two review modes:

- **Calibration review** — estimate 95% confidence intervals or point predictions for real-world socioeconomic, financial, and development indicators. Interval scoring treats the user's response as an implied distributional forecast, using answer-normalized log-likelihood to modulate review intervals via a continuous FSRS model. Designed to build calibrated order-of-magnitude intuitions relevant to GJOpen/Metaculus-style forecasting.

- **Generation review** — type-in recall of factual statements (currently CFA Level I LOS), progressing through letter-level masking stages before graduating to standard FSRS v6 scheduling. Supports massed practice (transient, no DB writes) and ordered practice (ring-buffer drilling) alongside the persistent global review queue.

An [Anki with Uncertainty](https://github.com/Sage-Future/anki-with-uncertainty) export pipeline is maintained for the calibration decks as a sharing and backup mechanism.

## Calibration Decks

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

Cross-cutting deck with distribution summary cards (mean, median, SD, min, max with entities) for each indicator across all source decks.

---

**Data sources:** World Bank WDI (API) for the thematic decks, GHS-UCDB for urban areas. Each card includes reference-class context (world average + regional average) to support Fermi-style reasoning.

## Generation Decks

Currently covers CFA Level I Learning Outcome Statements (225 statements across 48 readings). The generation review system is domain-agnostic and designed to expand to other factual recall content.

**Review lifecycle:**
1. **Generation phase** — cards progress through 3 masking levels (30%, 60%, first-letter-only), with queue-based spacing between presentations
2. **Graduation** — 2 consecutive passes at maximum masking promotes a card to recall phase
3. **Recall phase** — standard FSRS v6 with Again/Hard/Good/Easy grading; cards that lapse with interval < 24h demote back to generation at level 2

**Practice modes** (transient, no DB writes):
- `--practice` — massed practice filtered by reading number(s); cards progress through masking then re-queue at end of deck
- `--ordered-practice` — ring-buffer drilling in fixed LOS order; pass/fail affects masking level but not queue position

## SRS Scheduling

### Calibration (continuous FSRS)

A continuous variant of FSRS v6 where score in [0,1] maps directly to stability updates — no binary lapse/success threshold. Key properties:

- **Power-law forgetting curve:** `R(t,S) = (1 + FACTOR*t/S)^DECAY`
- **Sigmoid recall/lapse blend:** smoothly interpolates between recall and lapse stability formulas based on score
- **Initial stability** scales exponentially with score (~10 min at score=0, ~6.9 days at score=1.0)
- **23 tunable parameters**, all documented with role and rationale

### Generation (standard FSRS v6)

Published default weights `W[0..18]`, 4-button discrete grading. Completely independent from the calibration scheduler.

### Statistics

Brier score, calibration rate, score distribution histograms, point prediction hit rates — viewable per deck or per indicator.

## Architecture

```
config.py (DECKS registry, ENTITIES)
    |
    v
fetch-data / fetch-urban-data / fetch-desc-stats --> data/{deck}/*.csv
    |                                                      |
    v                                                      v
srs-import --> data/srs.db --> review TUI           build-deck --> .apkg

data/cfa_level1_los.json --> gen-import --> data/srs.db --> review-gen TUI
```

The CSV intermediary makes manual corrections straightforward — edit a CSV, re-run `srs-import` or `build-deck`.

## Setup

```bash
uv sync                              # install dependencies

# Fetch calibration data
uv run fetch-data development        # World Bank --> data/development/*.csv
uv run fetch-data tech_adoption
uv run fetch-data conflict_security
uv run fetch-data finance
uv run fetch-data education
uv run fetch-data governance
uv run fetch-urban-data              # GHS-UCDB --> data/urban_areas/*.csv
uv run fetch-desc-stats              # compute stats --> data/descriptive_stats/*.csv

# Calibration review
uv run srs-import --all              # import all decks --> data/srs.db
uv run review                        # launch TUI review session
uv run review --stats                # stats screen only

# Generation review (CFA LOS)
uv run gen-import                    # import LOS --> data/srs.db
uv run review-gen                    # launch TUI review session
uv run review-gen --practice 36      # massed practice: single reading
uv run review-gen --ordered-practice all  # ordered practice: all readings

# Anki export (sharing/backup)
uv run build-deck development        # --> knowledge_base.apkg

uv run pytest                        # 391 tests
```

Anki export requires the [Anki with Uncertainty](https://www.quantifiedintuitions.org/anki-with-uncertainty) add-on (code `694813595`).

## Project Structure

```
src/knowledge_base/
    config.py              # DECKS registry, entity lists, indicator metadata
    card_gen.py            # Question/answer/tag generation (shared by build_deck + srs)
    wb_api.py              # World Bank API client
    ghsl.py                # GHS-UCDB GeoPackage reader
    fetch_data.py          # World Bank --> data/<deck>/*.csv
    fetch_urban_data.py    # GHS-UCDB --> data/urban_areas/*.csv
    fetch_desc_stats.py    # Compute descriptive statistics
    desc_stats.py          # Statistics computation helper
    build_deck.py          # CSV --> .apkg (Anki export)
    srs/
        scoring.py         # Log-likelihood interval scoring, point prediction scoring
        scheduler.py       # Continuous FSRS scheduling (calibration mode)
        fsrs.py            # Standard FSRS v6 scheduling (generation mode)
        db.py              # SQLite schema, CRUD, migrations
        importer.py        # CSV --> SQLite card import (calibration)
        generation_db.py   # Generation card tables and CRUD
        generation_import.py  # JSON LOS --> SQLite card import
        generation_tui.py  # TUI for generation card review
        masking.py         # Letter-level masking algorithm (3 levels)
        text_scoring.py    # Token-level Levenshtein comparison
        stats.py           # Calibration metrics and score distributions
        tui.py             # TUI for calibration review sessions
data/
    development/           # Curated CSVs (gitignored, regenerated by fetch commands)
    tech_adoption/
    conflict_security/
    finance/
    education/
    governance/
    urban_areas/
    descriptive_stats/
    cfa_level1_los.json    # CFA Level I LOS data (checked in)
    srs.db                 # Personal review state (gitignored)
tests/                     # 391 tests
```

## Tag Schema

Calibration cards are tagged for filtering:

- `category::development`, `category::health`, `category::energy`, etc.
- `indicator::gdp_pc_ppp`, `indicator::internet_users`, etc.
- `entity::india`, `entity::sub_saharan_africa`, etc.
- `entity_type::region`, `entity_type::major`, `entity_type::long_tail`
- `era::1960`, `era::1990`, `era::2000`, `era::2010`, `era::current`
- `source_deck::development`, etc. (descriptive stats cards only)
