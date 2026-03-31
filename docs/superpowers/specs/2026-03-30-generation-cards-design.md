# Generation Cards: Graduated Masking → Typed Recall for CFA LOS Statements

**Date:** 2026-03-30
**Status:** Design

## Overview

A new card type for memorizing CFA Level I Learning Outcome Statements (LOS) through graduated text masking that progresses to pure typed recall. This system is completely separate from the existing interval/point estimation cards — separate table, separate scheduler, separate TUI entry point.

The core idea: cards begin in a **generation phase** where the answer is displayed with progressive letter masking (light → heavy → first-letters-only). Through massed intra-session practice, the learner builds familiarity with the text. After demonstrating mastery at maximum masking, the card **graduates** to a **recall phase** where the learner must type the full answer from memory, scheduled via standard FSRS v6 with 4-button grading.

### Learning Science Rationale

- **Generation effect** (Slamecka & Graf): producing words from partial cues creates stronger memory traces than passive recognition
- **Scaffolded withdrawal** (Bjork's desirable difficulties): systematically removing support as competence builds keeps the learner in the zone of proximal development
- **Retrieval practice** as the terminal mode: pure recall from a bare question is the strongest known technique for durable long-term memory

## Scope

- LOS statements only (not terminology definitions, not formulas)
- CFA Level I curriculum: 48 readings, ~200+ individual LOS statements across 3 SchweserNotes books
- Source data: extracted from SchweserNotes 2024 Level I CFA Books 1-3 LOS pages

## Architecture

### Separation from Existing System

| Concern | Interval/Point Cards | Generation/Recall Cards |
|---------|---------------------|------------------------|
| Table | `cards` | `generation_cards` |
| Scheduler | `scheduler.py` (continuous FSRS, experimental) | `fsrs.py` (standard FSRS v6, 4-button) |
| Scoring | `scoring.py` (log-likelihood, relative error) | Token-level text comparison + self-grading |
| TUI | `uv run review` | `uv run review-gen` |
| Review log | `review_log` (shared table, different `answer_mode` values) |

The continuous FSRS scheduler (`scheduler.py`) is an experimental adaptation for continuous score inputs from interval estimation. The generation cards use a standard, well-tested FSRS v6 implementation with discrete grades (Again/Hard/Good/Easy), which has been validated across millions of reviews in the open-spaced-repetition ecosystem.

### Module Layout

```
src/knowledge_base/srs/
    fsrs.py              # Standard FSRS v6 (4-button discrete grades)
    generation_db.py     # Schema, CRUD, migrations for generation_cards
    generation_import.py # LOS text → generation_cards population
    generation_tui.py    # Textual TUI for generation card review
    masking.py           # Letter-level masking algorithm
    text_scoring.py      # Token-level Levenshtein comparison
    # Existing files unchanged:
    db.py                # Interval card schema (untouched)
    scheduler.py         # Continuous FSRS (untouched)
    scoring.py           # Interval/point scoring (untouched)
    tui.py               # Interval card TUI (untouched)
```

## Data Model

### `generation_cards` Table

```sql
CREATE TABLE generation_cards (
    card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    deck                   TEXT    NOT NULL,       -- e.g. "cfa_level1"
    topic_id               TEXT    NOT NULL,       -- reading number, e.g. "1"
    los_id                 TEXT    NOT NULL,       -- e.g. "1.a"
    question               TEXT    NOT NULL,       -- "What is LOS 1.a?"
    answer                 TEXT    NOT NULL,       -- full LOS statement text
    tags                   TEXT    NOT NULL DEFAULT '[]',
    -- Generation phase state
    masking_level          INTEGER NOT NULL DEFAULT 0,  -- 0, 1, 2
    phase                  TEXT    NOT NULL DEFAULT 'generation',  -- 'generation' | 'recall'
    consecutive_max_passes INTEGER NOT NULL DEFAULT 0,  -- toward graduation (need 2)
    -- FSRS scheduling state (dormant during generation phase)
    difficulty             REAL    NOT NULL DEFAULT 5.0,
    stability              REAL    NOT NULL DEFAULT 0.0,
    last_review            TEXT,
    due                    TEXT,
    reps                   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (deck, los_id)
);
```

FSRS columns (`difficulty`, `stability`, `last_review`, `due`, `reps`) are dormant during the generation phase and only become active upon graduation to the recall phase. Default values are FSRS v6 defaults for a new card (difficulty 5.0, stability 0.0).

### Review Log

A new `generation_review_log` table mirrors the structure of `review_log` but references `generation_cards`:

```sql
CREATE TABLE generation_review_log (
    review_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL REFERENCES generation_cards(card_id),
    timestamp       TEXT    NOT NULL,
    answer_mode     TEXT    NOT NULL,   -- 'generation' | 'recall'
    phase_level     INTEGER,           -- masking level at time of review (generation phase)
    grade           INTEGER,           -- 1-4 FSRS grade (recall phase only)
    passed          INTEGER,           -- 1/0 (generation phase only)
    elapsed_days    REAL    NOT NULL,
    interval_applied REAL              -- recall phase only
);
```

Separate from `review_log` to avoid foreign key conflicts (`card_id` namespaces differ between `cards` and `generation_cards`) and because the columns differ (no `user_lower`/`user_upper`/`user_point`/`true_answer`; gains `phase_level`, `grade`, `passed`).

## Card Lifecycle

### Generation Phase (Intra-Session, Queue-Based)

No scheduler involvement. Cards are managed by queue position within a review session.

**Three masking levels:**

| Level | Masking | Description |
|-------|---------|-------------|
| 0 | ~30% of non-first letters | Light — recognition with generation effect |
| 1 | ~60% of non-first letters | Medium — real effort to reconstruct |
| 2 | First letters only | Maximum — one step from pure recall |

**Progression rules:**

- **Pass** → advance to next masking level, re-insert card after N+1 cards (where N = new level: so after 1, 2, 3 intervening cards)
- **Fail** → reset to level 0, re-insert after 1 intervening card

**Graduation gate:**

- Requires 2 consecutive passes at level 2 (first-letters-only)
- The second attempt must be separated from the first by at least 5 intervening card reviews
- Upon graduation: `phase` set to `'recall'`, FSRS state initialized as a new card

### Recall Phase (Standard FSRS v6)

Pure typed recall with no visual hints.

**Grading:** 4-button classic FSRS

| Button | Grade | Keyboard | Meaning |
|--------|-------|----------|---------|
| Again | 1 | `1` | Complete failure, couldn't recall |
| Hard | 2 | `2` | Recalled but with significant difficulty |
| Good | 3 | `3` | Recalled with acceptable effort |
| Easy | 4 | `4` | Effortless, immediate recall |

Grades feed into the standard FSRS v6 algorithm to compute the next review interval.

**Regression rule:** If a card receives **Again** AND the computed next interval is less than 24 hours, the card demotes back to the generation phase at **level 2** (first-letters-only). Rationale: the learner already built up through the scaffolding once, so they just need a refresher at the hardest scaffold before re-attempting pure recall. The 24-hour threshold prevents regression for cards that are well-established but had a momentary lapse — those just get a shorter FSRS interval.

## Masking Algorithm

Adapted from the reader app's generation masking system (`generationMask.ts`).

### Principles

- First letter of each word is always preserved at all levels
- Deterministic: seeded by `card_id + masking_level` so the same card at the same level always shows the same mask pattern (prevents gaming by memorizing revealed letters rather than content)
- Non-consecutive masked positions: avoid `__` runs for readability

### Masking Eligibility

**Always masked** (eligible words):
- Content words: nouns, verbs, adjectives, adverbs — the semantically meaningful terms

**Never masked:**
- Function words: a, an, and, are, as, at, be, by, for, from, in, is, it, its, of, on, or, that, the, their, them, to, was, were, which, with
- Short words (≤3 letters): masking these provides no useful generation effect
- Numbers and numeric expressions (e.g., "95%", "1-year")
- Abbreviations and acronyms (e.g., "CAPM", "NPV", "PV", "FSRS")
- Punctuation, commas, periods

### Level Behavior

- **Level 0 (~30%):** For each eligible word, mask ~30% of non-first letters. Select non-consecutive positions.
- **Level 1 (~60%):** For each eligible word, mask ~60% of non-first letters. Select non-consecutive positions.
- **Level 2 (first-letter-only):** All letters after the first are masked. `interpret` → `i________`

### Seeding

```python
seed = hash(f"{card_id}:{masking_level}")
```

Per-word seed derived from the global seed plus word index, ensuring deterministic but varied masking patterns within a card.

## Text Scoring (Display Only)

Text comparison is used for display feedback (highlighting correct/incorrect words), not for scheduling decisions. Scheduling is entirely self-graded.

**Token-level comparison:**
1. Tokenize both typed answer and correct answer into words (lowercase, strip punctuation)
2. Align tokens sequentially
3. Per-token scoring:
   - **Exact match** → green
   - **Levenshtein distance ≤ 1** (one typo) → yellow (accepted)
   - **No match** → red
4. Display side-by-side or inline diff

This provides feedback for the learner to make an informed self-grade decision. Getting 90% of a 30-word statement right might be "Good" or "Hard" depending on which words were missed.

## Standard FSRS v6 Implementation (`fsrs.py`)

A clean implementation of FSRS v6 with the published default parameters. Completely independent from `scheduler.py`.

### Key Differences from `scheduler.py`

| Aspect | `scheduler.py` (continuous) | `fsrs.py` (standard) |
|--------|---------------------------|---------------------|
| Input | Continuous score [0,1] | Discrete grade 1-4 (Again/Hard/Good/Easy) |
| Blend | Sigmoid recall/lapse blend | Binary: grade 1 = lapse, grade 2-4 = recall |
| Parameters | Custom-tuned 23 params | Published FSRS v6 defaults (19 weights) |
| Validation | Experimental | Validated on millions of reviews |

### Published Default Weights

Uses the FSRS v6 default parameter vector `w[0..18]` as published by the open-spaced-repetition project. These can be optionally tuned later from personal review data using the FSRS optimizer.

### Core API

```python
def schedule(card_state, grade, now) -> SchedulingResult:
    """Compute new card state after a review.

    card_state: (difficulty, stability, reps, last_review)
    grade: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
    Returns: new (difficulty, stability, due, reps)
    """
```

## TUI Design (`generation_tui.py`)

### Entry Point

```bash
uv run review-gen [deck]        # launch generation card review
uv run review-gen --stats       # stats screen
uv run review-gen --limit N     # cap session size
```

### Session Composition

A session contains both generation-phase and recall-phase cards:
- **Recall-phase cards** are loaded from DB: overdue first (by `due` date), then new cards
- **Generation-phase cards** are managed in an in-memory queue with position-based spacing
- Both are interleaved in a single review stream

### Generation Phase Display

```
cfa_level1 > LOS 1.a  [3/24]  (generation — level 1/2)

LOS 1.a:

i_t_r_r_t  interest  rates  as  r_q_i_e_  rates  of  r_t_r_,
d_s_o_n_  rates,  or  o_p_r_u_i_y  c_s_s  and  e_p_a_n  an
interest  rate  as  the  sum  of  a  real  r_s_-f_e_  rate
and  p_e_i_m_  that  c_m_e_s_t_  i_v_s_o_s  for  b_a_i_g
d_s_i_c_  types  of  risk

> [type your answer here]
```

On submit:
1. Show word-by-word diff (green/yellow/red highlighting)
2. Binary decision: **Pass** (Space/Enter) or **Fail** (f)
3. Card re-queued per progression rules

### Recall Phase Display

```
cfa_level1 > LOS 1.a  [7/24]  (recall)

What is LOS 1.a?

> [type your answer here]
```

On submit:
1. Show typed vs. correct with word-level diff highlighting
2. Show full correct answer for comparison
3. Four-button grade: **Again** (1) / **Hard** (2) / **Good** (3) / **Easy** (4)
4. Show computed next review interval

### Keybindings

| Key | Context | Action |
|-----|---------|--------|
| Enter | Input focused | Submit answer |
| Space/Enter | After feedback shown (generation) | Pass |
| f | After feedback shown (generation) | Fail |
| 1/2/3/4 | After feedback shown (recall) | Grade Again/Hard/Good/Easy |
| Ctrl+Q | Any | Quit |
| Ctrl+S | Any | Toggle stats screen |

## LOS Import Pipeline

### Data Source

LOS text extracted from SchweserNotes 2024 Level I CFA Books 1-3. Stored as a static data file (JSON or TOML) in the repository since there are ~200 items and they change only with curriculum revisions.

### Format

```json
{
  "deck": "cfa_level1",
  "readings": [
    {
      "number": 1,
      "title": "Rates and Returns",
      "los": [
        {
          "id": "1.a",
          "text": "interpret interest rates as required rates of return, discount rates, or opportunity costs and explain an interest rate as the sum of a real risk-free rate and premiums that compensate investors for bearing distinct types of risk"
        },
        {
          "id": "1.b",
          "text": "calculate and interpret different approaches to return measurement over time and describe their appropriate uses"
        }
      ]
    }
  ]
}
```

### Import Command

```bash
uv run gen-import                # import all LOS from data file
uv run gen-import --db PATH      # custom DB path
```

The importer reads the JSON, generates questions (`"What is LOS {id}?"`) and upserts into `generation_cards`. Idempotent — preserves scheduling state on re-import (same as interval card importer behavior).

### Question Format

- Question: `"What is LOS {id}?"`
- Answer: The LOS text as-is (lowercase start, no trailing period — matching the source)
- Tags: `["reading::{number}", "topic::{title_slug}", "book::{1|2|3}"]`

## Stats

The stats screen (`Ctrl+S` or `--stats`) shows:

- Total generation cards / recall cards
- Cards by phase (generation vs. recall)
- Cards by masking level (for generation phase)
- Graduation rate (how many have made it to recall)
- For recall-phase cards: grade distribution, average interval, retention rate

## Future Considerations (Out of Scope)

- **Terminology/formula cards:** Could use the same system with different content. Deferred — LOS statements only for now.
- **FSRS optimizer:** Once enough recall-phase review data accumulates, the default FSRS weights could be tuned. Same infrastructure as the parameter tuning design for interval cards.
- **Cross-deck review:** Reviewing CFA cards and indicator cards in a single session. Explicitly deferred — these are separate workflows.
