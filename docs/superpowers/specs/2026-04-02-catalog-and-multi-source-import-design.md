# Catalog TUI & Multi-Source Import Design

**Date:** 2026-04-02
**Status:** Approved
**Builds on:** [Generation Cards Design](2026-03-30-generation-cards-design.md)

## Problem

The `--practice` and `--ordered-practice` flags work well for drilling CFA LOS cards by reading number, but as material expands to include elaboration sources (official reading overviews, Schweser key concepts) and eventually other domains, the flat reading-number CLI becomes insufficient for:

1. **Discovering** what material is available and how much exists
2. **Navigating** a growing hierarchy of domains, topics, sources, and sections
3. **Importing** new markdown-based study material into the system
4. **Quick drilling** of ad-hoc text without a formal import step

## Design

### 1. Data Model

Add source and section granularity to generation cards. The hierarchy becomes:

```
deck            "cfa_level1"
  topic_id      "1"                         (reading number)
    source      "los" | "official" | "schweser"  (card set identity)
      section   "1.a" | "1.2" | "1.3"      (section within source)
        cards   [bullet 0, bullet 1, ...]   (individual practice items)
```

#### Schema changes to `generation_cards`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `source` | TEXT NOT NULL | `"los"` | Card set identity. Migration backfills existing cards. |
| `section_title` | TEXT | NULL | Display context, e.g., "Interest Rates and Time Value of Money" |
| `card_index` | INTEGER NOT NULL | `0` | Position within section, for ordering |

#### Key changes

- **Rename `los_id` → `section_id`**: Generalizes the field. Existing LOS cards keep their values (`"1.a"`, `"2.c"`, etc.).
- **Unique constraint**: Changes from `(deck, los_id)` to `(deck, source, topic_id, section_id, card_index)`.
- **Tags**: Existing `reading::N`, `topic::slug`, `book::N` tags preserved. New `source::X` tag added.

#### Mapping for existing LOS cards

| Field | Value |
|-------|-------|
| `source` | `"los"` |
| `section_id` | Current `los_id` value (e.g., `"1.a"`) |
| `section_title` | NULL (LOS cards show the LOS ID as context, no separate title needed) |
| `card_index` | `0` (one card per section) |

#### Mapping for elaboration sources

**Official Overview** (section-keyed, e.g., `- 1.2: Interest Rates and Time Value of Money`):
- `source = "official"`
- `section_id = "1.2"`
- `section_title = "Interest Rates and Time Value of Money"`
- `card_index = 0, 1, 2` (one per bullet under that section)

**Schweser Key Concepts** (LOS-keyed, e.g., `### LOS 1.a`):
- `source = "schweser"`
- `section_id = "1.a"`
- `section_title = NULL` (LOS ID is sufficient context)
- `card_index = 0, 1, 2, 3` (one per bullet under that LOS heading)

### 2. Markdown Import Pipeline

A single command for importing markdown study material:

```bash
gen-import-md <file> --deck cfa_level1 --topic 1 --source official
```

#### Heading convention auto-detection

The parser recognizes two formats:

1. **Section-keyed**: Matches patterns like `## 1.2: Title`, `- 1.2: Title`, or `### 1.2 Title`. Extracts the numeric section ID and title.
2. **LOS-keyed**: Matches patterns like `### LOS 1.a`, `### LOS 1.b`. Extracts the LOS identifier as section ID.

Detection is based on the first heading that matches either pattern. If neither matches, the importer exits with an error suggesting `--format section|los` to force interpretation.

#### Parsing rules

- Bullet points (`- `) under a recognized section heading become individual cards.
- Sub-bullets are folded into their parent bullet, preserving the full thought as one card.
- Consecutive non-bullet lines under a heading are joined into a single card (paragraph mode).
- Cards receive `card_index` 0, 1, 2... in document order within their section.
- Content before the first recognized section heading is skipped.
- Empty sections (heading with no bullets) are skipped.

#### Flags

| Flag | Purpose |
|------|---------|
| `--deck` (required) | Target deck name |
| `--topic` (required) | Topic/reading number |
| `--source` (required) | Source identifier (e.g., `"official"`, `"schweser"`) |
| `--preview` | Print parsed sections and card counts without writing to DB |
| `--format section\|los` | Force heading format detection (optional, auto-detected by default) |

#### Idempotent upsert

Same pattern as existing `gen-import`. Unique key is `(deck, source, topic_id, section_id, card_index)`. Re-importing the same file updates card content without duplicating. Since elaboration cards are primarily used in massed/ordered practice (no persistent SRS state at risk), re-indexing from content changes is safe.

### 3. Paste-and-Drill Mode

Quick-entry path for ad-hoc text memorization:

```bash
review-gen --paste                    # interactive: prompts for text input
echo "..." | review-gen --paste       # pipe from stdin
```

#### Flow

1. Accepts text via interactive prompt or stdin.
2. Splits into cards. Default: sentence boundaries (period + space/newline). Alternative: `--split-by line` for pre-formatted text (one card per line).
3. Immediately enters ordered-practice mode with the parsed cards.
4. On quit, cards are discarded (ephemeral by default).

#### Persisting

```bash
review-gen --paste --save-as "chapter3_definitions" --deck my_deck --topic 3 --source custom
```

When `--save-as` is provided along with deck/topic/source, the parsed cards are written to the DB before practice begins. They then appear in the catalog for future sessions. The `--save-as` value is used only in the confirmation message (e.g., `Saved 8 cards as "chapter3_definitions"`); it is not stored in the data model. The `--source` value is the source identifier in the DB.

### 4. Catalog TUI

The new default screen when running bare `review-gen` (when no `--practice`, `--ordered-practice`, or `--paste` flags are provided and no recall-phase cards are due).

#### Layout

```
┌─ Generation Card Catalog ──────────────────────────────┐
│                                                         │
│  CFA Level I                                            │
│  ├── Reading 1: Rates and Returns                       │
│  │   ├── LOS (5 cards)                                  │
│  │   ├── Official Overview (18 cards)                   │
│  │   │   ├── 1.2: Interest Rates and TVM (3)            │
│  │   │   ├── 1.3: Rates of Return (4)                   │
│  │   │   ├── 1.4: Money vs Time-Weighted (2)            │
│  │   │   ├── 1.5: Annualized Return (2)                 │
│  │   │   └── 1.6: Other Return Measures (5)             │
│  │   └── Schweser Key Concepts (5 cards)                │
│  │       ├── LOS 1.a (4)                                │
│  │       ├── LOS 1.b (2)                                │
│  │       └── ...                                        │
│  ├── Reading 2: ...                                     │
│  └── ...                                                │
│                                                         │
│  [Enter] Expand/Collapse  [Space] Select                │
│  [m] Massed  [o] Ordered  [p] Paste  [q] Quit          │
└─────────────────────────────────────────────────────────┘
```

#### Tree structure

The tree is built dynamically from cards in the database, grouped by:

1. **Deck** (top level) — e.g., "CFA Level I"
2. **Topic** — e.g., "Reading 1: Rates and Returns" (topic_id + reading title from card metadata)
3. **Source** — e.g., "LOS", "Official Overview", "Schweser Key Concepts" (human-readable labels derived from source field)
4. **Section** (leaf for multi-card sources) — e.g., "1.2: Interest Rates and TVM (3)" showing section_id, section_title, and card count

For LOS source (one card per section), sections are not shown — the source node is the leaf.

#### Navigation & selection

| Key | Action |
|-----|--------|
| Up/Down, j/k | Navigate tree |
| Enter | Expand/collapse node |
| Space | Toggle selection on current node |
| m | Launch massed practice with selected cards |
| o | Launch ordered practice with selected cards |
| p | Enter paste-and-drill mode |
| q | Quit |

#### Selection semantics

- Selecting a parent node selects all its children.
- Deselecting a parent deselects all children.
- Selecting individual children without the parent is allowed (partial selection).
- The footer shows a count of selected cards: `"12 cards selected"`.

#### Multi-select across levels

Users can select at any granularity and combine:
- "Reading 1" (all sources) + "Reading 2 > LOS" (just LOS for reading 2) = valid selection
- The practice session receives the union of all selected cards

### 5. CLI Shortcuts

Existing flags continue to work. New flags extend filtering:

```bash
# Existing (backwards compatible, implicitly source="los")
review-gen --ordered-practice 1-5
review-gen --practice 1,3,5

# New: source-aware shortcuts
review-gen --source official --topic 1 --ordered-practice
review-gen --source schweser --section 1.a --ordered-practice
review-gen --source official --topic 1 --section 1.2-1.4 --massed-practice
```

| Flag | Purpose |
|------|---------|
| `--source` | Filter by source (e.g., `official`, `schweser`, `los`) |
| `--topic` | Filter by topic/reading number (supports reading spec syntax: `1`, `1-5`, `1,3,5`, `all`) |
| `--section` | Filter by section ID (supports range syntax like topic) |

When `--practice` or `--ordered-practice` is used without `--source`, it defaults to `source="los"` for backwards compatibility.

### 6. Practice Session Display

#### Header format

Cards display contextual headers showing their position in the hierarchy:

**LOS cards** (unchanged):
```
cfa_level1 > 1.a [3/5] (ordered — level 1/2)
```

**Elaboration cards** (with section context):
```
cfa_level1 > official > 1.2: Interest Rates and TVM [2/3] (ordered — level 1/2)
```

**Schweser cards**:
```
cfa_level1 > schweser > LOS 1.a [3/4] (ordered — type-in)
```

The `[N/M]` counter reflects position within the current section when practicing a single section, or within the full selection when practicing across sections.

#### Card content

The masked/type-in content is the individual bullet text, identical to how LOS statements are presented today. The masking algorithm, scoring, and pass/fail mechanics are unchanged.

### 7. Global Review Integration

Elaboration cards imported persistently participate in the full generation lifecycle:

1. **Generation phase**: masking levels 0 → 1 → 2 → type-in, with graduation after 2 consecutive passes at max masking (same as LOS cards)
2. **Recall phase**: standard FSRS v6 scheduling with Again/Hard/Good/Easy (same as LOS cards)
3. **Regression rule**: recall-phase cards with Again + interval < 24h demote back to generation at level 2 (same as LOS cards)

No changes to the lifecycle mechanics. The only difference is that elaboration cards have richer metadata (source, section_title) for display purposes.

Ephemeral paste-and-drill cards never enter global review.

### 8. Migration

A single schema migration on `generation_cards`:

1. Add column `source TEXT NOT NULL DEFAULT 'los'`
2. Add column `section_title TEXT`
3. Add column `card_index INTEGER NOT NULL DEFAULT 0`
4. Rename column `los_id` → `section_id`
5. Drop unique constraint `(deck, los_id)`
6. Add unique constraint `(deck, source, topic_id, section_id, card_index)`
7. Increment `schema_version`

All existing cards automatically get `source='los'`, `card_index=0`, and `section_id` = their former `los_id` value. No data loss, no re-import needed.

### 9. New Files

| File | Purpose |
|------|---------|
| `srs/md_importer.py` | Markdown parser and import pipeline (`gen-import-md` entry point) |
| `srs/catalog.py` | Catalog TUI screen (Textual widget, tree builder, selection logic) |

Modifications to existing files:
- `generation_db.py` — schema migration, new query functions for source/section filtering, rename los_id references
- `generation_tui.py` — integrate catalog as default screen, add `--paste`/`--source`/`--section` flags, update header display
- `generation_import.py` — add source/section_title/card_index fields to LOS import
- `pyproject.toml` — add `gen-import-md` script entry point
