# CLAUDE.md

## Project Overview

TUI-based initial-encoding aid for drilling structured study material through progressive masking and massed/ordered practice. Import markdown study notes or paste raw text, then drill through masking levels that build recall. A catalog TUI lets you browse and select material across multiple sources and topics. Once material reaches 3+ successful passes, export to Anki for long-term spaced retrieval via FSRS.

## Quick Reference

```bash
uv sync                              # install deps

# Generation review (primary feature)
uv run gen-import                       # import LOS JSON → data/srs.db
uv run gen-import-md <file> --deck D --topic T --source S  # import markdown
uv run gen-import-md <file> ... --preview  # preview parse without importing
uv run review-gen                       # launch catalog TUI (browse & select)
uv run review-gen [deck]                # launch with deck filter
uv run review-gen --stats               # stats screen only
uv run review-gen --limit N             # cap session size
uv run review-gen --practice 36         # massed practice: single reading (LOS)
uv run review-gen --practice 1-5        # massed practice: reading range (LOS)
uv run review-gen --practice 1,3,5      # massed practice: specific readings (LOS)
uv run review-gen --practice all        # massed practice: all readings (LOS)
uv run review-gen --ordered-practice 36   # ordered practice: single reading (LOS)
uv run review-gen --ordered-practice 1-5  # ordered practice: reading range (LOS)
uv run review-gen --ordered-practice 1,3,5 # ordered practice: specific readings (LOS)
uv run review-gen --ordered-practice all  # ordered practice: all readings (LOS)
uv run review-gen --source S --topic T --ordered-practice  # source-filtered practice
uv run review-gen --source S --section X --ordered-practice  # section-filtered practice
uv run review-gen --start-level 2       # start at max masking for familiar material
uv run review-gen --paste               # paste text for ephemeral drill
uv run review-gen --paste --save-as N --deck D --topic T --source S  # persist pasted text
uv run gen-import-csv <file> --deck D --source S         # import CSV exact-answer cards
uv run gen-import-csv <file> --deck D --source S --preview  # preview without importing
uv run gen-import-csv <file> --deck D --source S --topic T  # override topic

uv run pytest                        # ~314 tests
```

## Architecture

```
# Generation review pipeline
markdown files ──→ gen-import-md ──→ data/srs.db ──→ review-gen TUI
cfa_level1_los.json ──→ gen-import ─┘                    │
                                                   catalog TUI (browse/select)
```

### Generation review (`srs/`)
- `generation_db.py` — `generation_cards` and `generation_review_log` tables, CRUD, schema v3 (source/section_id/card_index/card_type)
- `generation_import.py` — JSON LOS data → SQLite card population
- `md_importer.py` — markdown parser (section-keyed + LOS-keyed formats) and `gen-import-md` CLI
- `catalog.py` — `CatalogNode` tree builder and `CatalogScreen` Textual widget for browsing/selecting material
- `generation_tui.py` — Textual TUI for generation card review, catalog entry point, paste-and-drill
- `masking.py` — letter-level masking algorithm (3 levels: 30%, 60%, first-letter-only)
- `csv_importer.py` — CSV parser and `gen-import-csv` CLI for exact-answer cards
- `text_scoring.py` — token-level Levenshtein comparison for feedback display, numeric-aware exact matching
- `fsrs.py` — standard FSRS v6 scheduler (4-button: Again/Hard/Good/Easy), used for recall phase

## Key Constraints

### Generation cards (multi-source)
- **Card types**: `masking` (progressive masking, default) and `exact` (Q&A with numeric-aware matching). Card type stored in `card_type` column.
- **Multi-source hierarchy**: deck → topic (reading) → source (los/official/schweser/custom) → section → cards. Schema v3 unique key: `(deck, source, topic_id, section_id, card_index)`.
- **Catalog TUI**: default entry when running bare `review-gen`. Tree browser with multi-select at any level, launches massed or ordered practice.
- **Markdown import** (`gen-import-md`): parses section-keyed (`- 1.2: Title`) and LOS-keyed (`### LOS 1.a`) markdown into cards. Auto-detects format.
- **CSV import** (`gen-import-csv`): imports exact-answer cards from CSV with `question` and `answer` columns. Optional `topic`, `section`, `tags` columns.
- **Paste-and-drill** (`--paste`): ephemeral text memorization. Sentence or line splitting. `--save-as` to persist.
- **Two review modes**: global review (masking → graduation → FSRS) and massed practice (transient, no DB writes)
- **Global review lifecycle**: generation phase (3 masking levels, queue-based spacing) → graduation (2 consecutive passes at max masking) → recall phase (standard FSRS v6 with Again/Hard/Good/Easy)
- **Massed practice** (`--practice`): in-memory only, no persistent state changes. Cards progress through masking levels → full type-in, then re-queue with randomized positional spacing (fail → position 1; pass → 2-4/4-8/8-12 cards back). Filter by reading number(s).
- **Per-card pass counter**: tracks type-in (masking) and correct answer (exact) passes per card in session. Displayed on answer screen, green at 3+.
- **Ordered practice** (`--ordered-practice`): like massed practice but cards cycle in fixed LOS order (ring buffer). Pass/fail affects masking level but not queue position — card always goes to back. User drills until they quit.
- **Start level** (`--start-level 0|1|2`): initial masking level for practice. Default 0 starts from easiest masking; 2 starts at max masking for familiar material.
- **Source-filtered practice**: `--source S --topic T --ordered-practice` drills cards from a specific source. Without `--source`, defaults to LOS cards for backwards compatibility.
- **Standard FSRS v6** (`fsrs.py`): published default weights `W[0..18]`, 4-button discrete grading. Used only for recall phase.
- **Regression rule**: recall-phase cards that get Again with interval < 24h demote back to generation at level 2.
- **LOS data**: `data/cfa_level1_los.json` — 225 statements across 48 CFA Level I readings. Not gitignored (checked in).

## Code Style

- Python 3.12+, managed with `uv`
- `textual` for TUI
- No type stubs or mypy — tests are the quality gate
- Tests use `pytest`

## Data

- `data/srs.db` is gitignored — personal review state, regenerated by `gen-import` or `gen-import-md`
- `data/cfa_level1_los.json` — checked in; source data for LOS card generation
