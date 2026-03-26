# Descriptive Statistics Deck Design

## Overview

A new Anki deck, **Knowledge Base::Descriptive Statistics**, that quizzes on the distributional properties (mean, median, standard deviation, range) of each indicator across the existing Knowledge Base decks. Uses the **Enhanced Cloze 2.1 v2** note type instead of the Interval (confidence interval) model used by the other decks.

## Motivation

The existing decks train calibration on individual entity values. This deck adds a "meta layer" — knowing the shape of each distribution helps contextualize individual data points and builds intuition for global variation.

## Data Sources

### World Bank indicators (4 decks)

For each indicator in `development`, `tech_adoption`, `conflict_security`, and `finance`:
- Fetch the **full cross-section** from the World Bank API (~190 countries), current era only
- Compute stats over **country-level rows only** (exclude regional aggregates like "World", "Sub-Saharan Africa")

### Urban indicators (1 deck)

For each indicator in `urban_areas`:
- Read the **existing** `data/urban_areas/*.csv` files (produced by `fetch-urban-data`)
- Filter to **city rows only** (exclude aggregate rows), most recent era per indicator
- Compute stats over the top-50 city values

## Pipeline

Two-stage, matching the existing architecture:

```
fetch-desc-stats  -->  data/descriptive_stats/*.csv  -->  build-deck descriptive_stats  -->  .apkg
```

### fetch-desc-stats

New CLI entry point. Produces one CSV per indicator in `data/descriptive_stats/`.

**World Bank indicators:**
1. Iterate every indicator across the 4 WB-based decks
2. Fetch all ~190 country codes from the WB API using each source deck's `era_ranges["current"]` year window, picking the most recent available year per country
3. Compute over country-level rows: mean, median, std dev, min (value + entity name), max (value + entity name), count
4. Write CSV

**Urban indicators:**
1. Read existing `data/urban_areas/*.csv`
2. Filter to city rows, most recent era
3. Compute same stats
4. Write CSV (prefixed with `urban_` to avoid name collisions, e.g. `urban_population.csv`)

### CSV schema

One row per indicator:

```
indicator_id,indicator_name,source_deck,unit_label,unit_prefix,decimals,scale_factor,year,n,mean,median,std,min_value,min_entity,max_value,max_entity
```

### build-deck descriptive_stats

Reads the summary CSVs, generates one Enhanced Cloze card per indicator, writes `knowledge_base_descriptive_stats.apkg`.

## Card Format

Uses the **Enhanced Cloze 2.1 v2** note type (model ID `1774552435321`, cloze type).

### Fields

| Field   | Content |
|---------|---------|
| Content | Cloze-deleted descriptive statistics sentence |
| Note    | Source attribution |
| Mnemonics | Empty |
| Extra   | Empty |
| Cloze99 | Empty |

### Templates

Loaded at build time from the installed add-on:
- `~/.local/share/Anki2/addons21/1990296174/note_type/Enhanced_Cloze_Front_Side.html`
- `~/.local/share/Anki2/addons21/1990296174/note_type/Enhanced_Cloze_Back_Side.html`
- `~/.local/share/Anki2/addons21/1990296174/note_type/Enhanced_Cloze_CSS.css`

Build fails with a clear error if these files are not found.

### Card examples

**World Bank indicator:**

> Across all 190 countries, GDP per capita (PPP) as of 2024 ranges from {{c1::$878}} (Burundi) to {{c2::$143,314}} (Luxembourg), with a mean of {{c3::$18,463}}, median of {{c4::$13,178}}, and standard deviation of {{c5::$22,147}}.

**Urban indicator:**

> Across the top 50 cities, CO2 emissions per capita as of 2020 ranges from {{c1::1.23}} tonnes/person (Kinshasa) to {{c2::18.45}} tonnes/person (Houston), with a mean of {{c3::6.78}}, median of {{c4::5.12}}, and standard deviation of {{c5::4.89}}.

### Tags

- `source_deck::{development|tech_adoption|conflict_security|finance|urban_areas}`
- `category::{indicator category}`

## Deck Config

New entry in `DECKS` in `config.py`:

- Key: `descriptive_stats`
- `name`: `"Knowledge Base::Descriptive Statistics"`
- `deck_id`: new unique int
- `output`: `"knowledge_base_descriptive_stats.apkg"`
- `data_dir`: `"data/descriptive_stats"`
- No `indicators` list or `era_ranges` — the summary CSVs are self-describing

## Code Changes

### New files
- `src/knowledge_base/fetch_desc_stats.py` — fetch orchestrator and stat computation
- `data/descriptive_stats/.gitkeep`

### Modified files
- `src/knowledge_base/config.py` — add `descriptive_stats` deck entry
- `src/knowledge_base/build_deck.py` — add Enhanced Cloze model, `_run_descriptive_stats()` function, dispatch in `_run()`/`main()`
- `pyproject.toml` — add `fetch-desc-stats` CLI entry point

### Untouched
- `fetch_data.py`, `fetch_urban_data.py`, `wb_api.py`, `ghsl.py`
- All existing deck configs
