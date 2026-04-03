# Knowledge Base

A TUI-based memorization tool for drilling structured study material through progressive masking and type-in practice.

## Core Feature: Generation Review

Import structured markdown or paste raw text, then drill it through a masking → type-in progression that builds recall. The system supports two markdown formats out of the box and a free-form paste mode for quick memorization of arbitrary text.

### Importing Material

**Structured markdown** — point at a `.md` file with either section-keyed or LOS-keyed headings:

```bash
# Section-keyed (e.g., "- 1.2: Interest Rates and TVM")
uv run gen-import-md notes.md --deck my_deck --topic 1 --source official

# LOS-keyed (e.g., "### LOS 1.a")
uv run gen-import-md schweser.md --deck my_deck --topic 1 --source schweser

# Preview what will be imported without writing to DB
uv run gen-import-md notes.md --deck my_deck --topic 1 --source official --preview
```

Each bullet point under a heading becomes an individual card. Sub-bullets fold into their parent.

**Paste-and-drill** — paste text directly for immediate practice:

```bash
uv run review-gen --paste                  # ephemeral: splits into sentences, drill, done
uv run review-gen --paste --split-by line  # split on newlines instead
uv run review-gen --paste --save-as "ch3_defs" --deck my_deck --topic 3 --source notes  # persist
```

### Practicing

```bash
uv run review-gen                          # catalog TUI: browse, select, launch
uv run review-gen --ordered-practice 1-5   # drill readings 1-5 in order
uv run review-gen --practice all           # massed practice, all readings
uv run review-gen --source official --topic 1 --ordered-practice  # source-filtered
uv run review-gen --start-level 2          # start at max masking for familiar material
```

**Catalog TUI** — the default when you run bare `review-gen`. A tree browser organized as deck → reading → source → section. Multi-select with Space, then press `m` for massed or `o` for ordered practice.

**Practice modes** (transient, no DB writes):
- **Massed** (`--practice`) — cards in random order, progressing through masking levels then re-queuing
- **Ordered** (`--ordered-practice`) — fixed document order (ring buffer); pass/fail affects masking level but not position

**Masking progression** — cards start with ~30% of letters masked, advance to ~60%, then first-letter-only hints, then full type-in. `--start-level 2` skips to max masking for material you already know.

### Global Review (Persistent SRS)

Cards imported persistently also participate in a long-term review lifecycle:

1. **Generation phase** — progress through 3 masking levels with queue-based spacing
2. **Graduation** — 2 consecutive passes at max masking promotes to recall phase
3. **Recall phase** — standard FSRS v6 (Again/Hard/Good/Easy); lapsing with interval < 24h demotes back to generation

```bash
uv run gen-import                    # import CFA LOS JSON data
uv run review-gen                    # global review picks up due cards automatically
```

## Secondary Feature: Calibration Review

A confidence-interval and point-prediction training system for building calibrated intuitions about real-world indicators. Interval scoring treats responses as implied distributional forecasts, using answer-normalized log-likelihood to modulate review intervals via a continuous FSRS model.

Eight decks spanning ~50 indicators across 47 countries and 50 major cities, sourced from World Bank WDI and GHS-UCDB. An [Anki with Uncertainty](https://github.com/Sage-Future/anki-with-uncertainty) export pipeline is maintained for sharing and backup.

```bash
uv run fetch-data development        # World Bank → data/development/*.csv
uv run srs-import --all              # import all decks → data/srs.db
uv run review                        # launch calibration TUI
uv run build-deck development        # export to .apkg for Anki
```

### Calibration Decks

| Deck | Indicators | Entities | Source |
|------|-----------|----------|--------|
| Development | GDP per capita, poverty, Gini, life expectancy, mortality, CO2, population, etc. (13) | 47 countries/regions | World Bank |
| Technology Adoption | Internet, mobile, broadband, R&D, high-tech exports, electricity access (6) | 47 | World Bank |
| Conflict & Security | Military spending, armed forces, arms imports, homicides, refugees (7) | 47 | World Bank |
| Finance & Markets | Inflation, reserves, market cap, credit, remittances (8) | 47 | World Bank |
| Education | Literacy, secondary/tertiary enrollment, education spending (4) | 47 | World Bank |
| Governance | 6 Worldwide Governance Indicators | 40 | World Bank |
| Urban Areas | Population, CO2, PM2.5, life expectancy, HDI, built-up area (6) | 50 cities | GHS-UCDB |
| Descriptive Statistics | Mean/median/SD/min/max summaries for all indicators above | cross-cutting | computed |

## Setup

```bash
uv sync                              # install dependencies

# Generation review (primary)
uv run gen-import                    # import LOS data → data/srs.db
uv run gen-import-md <file> --deck D --topic T --source S  # import markdown
uv run review-gen                    # launch catalog or review TUI

# Calibration review (secondary)
uv run fetch-data <deck_key>         # fetch World Bank data
uv run srs-import --all              # import calibration decks
uv run review                        # launch calibration TUI

uv run pytest                        # ~510 tests
```

## Architecture

```
# Generation review pipeline
markdown files ──→ gen-import-md ──→ data/srs.db ──→ review-gen TUI
cfa_level1_los.json ──→ gen-import ─┘                    │
                                                   catalog TUI (browse/select)

# Calibration review pipeline
config.py (DECKS, ENTITIES)
    │
    v
fetch-data / fetch-urban-data ──→ data/{deck}/*.csv
    │                                    │
    v                                    v
srs-import ──→ data/srs.db ──→ review TUI    build-deck ──→ .apkg
```

## Project Structure

```
src/knowledge_base/
    srs/
        # Generation review (primary)
        generation_db.py      # Schema v2 (source/section_id/card_index), CRUD
        generation_import.py  # JSON LOS → SQLite import
        md_importer.py        # Markdown parser + gen-import-md CLI
        catalog.py            # Catalog tree builder + CatalogScreen TUI
        generation_tui.py     # Review TUI, practice modes, paste-and-drill
        masking.py            # Letter-level masking (3 levels)
        text_scoring.py       # Token-level Levenshtein comparison
        fsrs.py               # Standard FSRS v6 (generation recall phase)

        # Calibration review (secondary)
        scoring.py            # Log-likelihood interval scoring
        scheduler.py          # Continuous FSRS (calibration mode)
        db.py                 # Calibration card schema, CRUD
        importer.py           # CSV → SQLite import
        tui.py                # Calibration review TUI
        stats.py              # Brier score, calibration metrics

    # Shared / calibration data pipeline
    config.py                 # DECKS registry, entity lists
    card_gen.py               # Question/answer generation
    wb_api.py                 # World Bank API client
    ghsl.py                   # GHS-UCDB reader
    fetch_data.py             # World Bank → CSV
    fetch_urban_data.py       # GHS-UCDB → CSV
    fetch_desc_stats.py       # Descriptive statistics
    build_deck.py             # CSV → .apkg (Anki export)

data/
    cfa_level1_los.json       # CFA Level I LOS data (checked in)
    srs.db                    # Review state (gitignored)
    {deck}/*.csv              # Calibration CSVs (gitignored)
```
