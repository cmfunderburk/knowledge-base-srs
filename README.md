# Knowledge Base

Two TUI tools for building and maintaining knowledge:

- **SRS (`review-gen`)** — initial-encoding aid for drilling structured study material through progressive masking, exact-answer Q&A, and massed/ordered practice. Import markdown notes, CSV data, or paste raw text, then drill until material is solid (3+ passes per card). Once encoded, export to Anki for long-term spaced retrieval via FSRS.
- **Code Review (`code-review`)** — Leitner-scheduled spaced practice for programming exercises. Write a solution in `$EDITOR`, run the exercise's tests, review a diff against the reference, then grade (Again/Hard/Good/Easy) to schedule the next repetition.

## Importing Material

**Structured markdown** — section-keyed or LOS-keyed headings:

```bash
uv run gen-import-md notes.md --deck my_deck --topic 1 --source official
uv run gen-import-md notes.md --deck my_deck --topic 1 --source official --preview
```

**CSV exact-answer cards** — for numerical/factual data:

```bash
uv run gen-import-csv data.csv --deck "Indicator Baselines" --source development
uv run gen-import-csv data.csv --deck "Indicator Baselines" --source development --preview
```

CSV requires `question` and `answer` columns. Optional: `topic`, `section`, `tags`.

**Paste-and-drill** — paste text directly for immediate practice:

```bash
uv run review-gen --paste                  # ephemeral: splits into sentences, drill, done
uv run review-gen --paste --split-by line  # split on newlines instead
uv run review-gen --paste --save-as "ch3_defs" --deck my_deck --topic 3 --source notes
```

**LOS JSON** — CFA Level I Learning Outcome Statements:

```bash
uv run gen-import                          # import data/cfa_level1_los.json → data/srs.db
```

## Practicing

```bash
uv run review-gen                          # catalog TUI: browse, select, launch
uv run review-gen --ordered-practice 1-5   # drill readings 1-5 in order
uv run review-gen --practice all           # massed practice, all readings
uv run review-gen --source official --topic 1 --ordered-practice  # source-filtered
uv run review-gen --start-level 2          # start at max masking for familiar material
```

**Catalog TUI** — the default when you run bare `review-gen`. A tree browser organized as deck > topic > source > section. Multi-select with Space, then press `m` for massed or `o` for ordered practice.

### Card Types

- **Masking cards** — progressive masking through 3 levels (30% masked > 60% > first-letter-only) then full type-in. Used for text-based material (markdown, paste, LOS).
- **Exact-answer cards** — question displayed, type the answer, checked via numeric-aware matching. Used for numerical/factual data (CSV import). Decorative prefixes (`~`, `$`) and unit suffixes (`%`, `years`, etc.) are normalized so you only need to type the core value.

### Practice Modes

Both modes are transient (no DB writes):

- **Massed** (`--practice` or `m` in catalog) — randomized order, randomized positional spacing on pass (2-4 / 4-8 / 8-12 cards back), fail goes right after the next card. Good for independent facts where order doesn't matter.
- **Ordered** (`--ordered-practice` or `o` in catalog) — fixed document order (ring buffer). Pass/fail affects masking level but not position. Good for interconnected material where sequence builds understanding.

A **per-card pass counter** tracks successful recalls in each session. Displayed on the answer screen; turns green at 3+ passes to signal the card has met the minimum encoding threshold.

## Global Review (Persistent SRS)

Cards imported persistently also participate in a long-term review lifecycle:

1. **Generation phase** — progress through 3 masking levels with queue-based spacing
2. **Graduation** — 2 consecutive passes at max masking promotes to recall phase
3. **Recall phase** — standard FSRS v6 (Again/Hard/Good/Easy); lapsing with interval < 24h demotes back to generation

## Code Review

Register an exercise directory, then use the TUI to drill it on a Leitner schedule:

```bash
uv run code-review add exercises/my-problem/   # register once
uv run code-review                             # launch exercise list TUI
```

**Exercise directory layout:**

```
exercises/
    my-problem/
        problem.md          # shown to user; first H1 becomes the title
        test_solution.py    # pytest tests — import from `submission`, not `solution`
        solution.py         # optional reference; shown as diff after grading
```

**TUI flow:** select an exercise → read the problem → `$EDITOR` opens a temp file → write your solution → tests run automatically → see pass/fail + diff vs. reference → press Again / Hard / Good / Easy to schedule the next repetition.

**Leitner schedule:** 5 boxes with intervals of 1 / 2 / 4 / 8 / 16 days. Again resets to box 1; Hard stays; Good advances one box; Easy advances two.

## Setup

```bash
uv sync                              # install dependencies
uv run gen-import                    # import LOS data (optional)
uv run review-gen                    # launch catalog TUI
uv run pytest                        # ~390 tests
```

## Architecture

```
markdown files ──→ gen-import-md ──→ data/srs.db ──→ review-gen TUI
CSV files ──→ gen-import-csv ────┘                       │
cfa_level1_los.json ──→ gen-import ─┘              catalog TUI (browse/select)

exercises/<slug>/ ──→ code-review add ──→ data/code_exercises.db ──→ code-review TUI
```

### Source Files (`src/knowledge_base/srs/`)

| File | Responsibility |
|------|---------------|
| `generation_db.py` | `generation_cards` and `generation_review_log` tables, CRUD, schema v3 |
| `generation_import.py` | JSON LOS data > SQLite import |
| `md_importer.py` | Markdown parser (section-keyed + LOS-keyed) and CLI |
| `csv_importer.py` | CSV parser for exact-answer cards and CLI |
| `catalog.py` | Catalog tree builder and Textual widget |
| `generation_tui.py` | Review TUI, practice modes, paste-and-drill |
| `masking.py` | Letter-level masking algorithm (3 levels) |
| `text_scoring.py` | Token-level Levenshtein comparison, numeric-aware exact matching |
| `fsrs.py` | Standard FSRS v6 scheduler (recall phase) |

### Source Files (`src/knowledge_base/code_review/`)

| File | Responsibility |
|------|---------------|
| `leitner.py` | 5-box Leitner scheduler; grade → box + due date |
| `db.py` | `code_exercises` + `code_review_log` tables, CRUD, atomic `record_grade()` |
| `runner.py` | pytest runner (writes/deletes `submission.py`) + unified diff |
| `cli.py` | `handle_add()` — validates and registers exercise directories |
| `tui.py` | `ExerciseListScreen`, `ReviewScreen`, `CodeReviewApp`, `main()` |
