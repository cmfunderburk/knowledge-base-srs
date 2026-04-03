# Massed Practice Expansion Design

## Goal

Expand the massed/ordered practice system to support exact-answer cards (numerical/factual Q&A) alongside the existing masking-progression cards. Redesign the massed practice reshuffling algorithm with randomized spacing. Add a per-card session pass counter to track progress toward the 3+ pass threshold before Anki handoff.

## Context

The project is being repositioned as an initial-encoding aid. The workflow is: import material → drill via massed/ordered practice until solid (3+ passes per card) → export to Anki for long-term FSRS scheduling. The current system handles text-based material well via progressive masking, but numerical/factual material (e.g., indicator statistics, ranges, key values) doesn't map onto the masking approach. These need a "normal" Q&A card type with exact-answer checking.

### Massed vs ordered practice philosophy

- **Ordered practice**: material where the inherent organization matters. LOS statements, LMO sections, KeyConcepts — interconnected topics where sequential learning builds understanding. Cards cycle in fixed order (ring buffer).
- **Massed practice**: material where independent recall matters. Indicator data, factual details — order doesn't provide context for answers. Cards are shuffled and respaced to prevent fixed-order dependencies.

## Data Model

### `generation_cards` table: add `card_type` column

Add `card_type TEXT NOT NULL DEFAULT 'masking'` to the `generation_cards` table. Values: `'masking'` (existing behavior) or `'exact'` (new exact-answer cards).

Schema version bumps from 2 to 3. Migration adds the column and sets all existing rows to `'masking'`.

**Exact-answer cards in the table:**
- `question` — the prompt (e.g., "CO2 emissions per capita, Europe and China?")
- `answer` — the exact answer string (e.g., "6.2"), stored verbatim
- `card_type` = `'exact'`
- `masking_level`, `consecutive_max_passes`, `phase` — unused, left at defaults (0, 0, `'generation'`)
- FSRS fields — unused, left at defaults
- `deck`, `source`, `topic_id`, `section_id`, `card_index` — used normally for organization and uniqueness

The existing unique constraint `(deck, source, topic_id, section_id, card_index)` works for both types.

## CSV Import: `gen-import-csv`

### CLI

```bash
uv run gen-import-csv data.csv --deck "Indicators" --source "knowledge_base"
uv run gen-import-csv data.csv --deck "Indicators" --source "knowledge_base" --preview
uv run gen-import-csv data.csv --deck "Indicators" --source "knowledge_base" --topic "GDP"
```

Required flags: `--deck`, `--source`.

Optional: `--topic` (defaults to filename without extension).

### CSV format

Required columns: `question`, `answer`

Optional columns:
- `topic` — overrides `--topic` per row
- `section` — defaults to `"1"`
- `tags` — JSON array or comma-separated string

All cards are inserted with `card_type='exact'`. `card_index` is auto-assigned per section (row order within each section group).

### Preview mode

`--preview` prints parsed card count by topic/section, sample Q&A pairs, no DB writes. Same pattern as `gen-import-md --preview`.

### Answer storage

The CSV `answer` column is stored verbatim as a string. Numeric-aware matching happens at review time, not import time. This keeps storage simple and round-trip safe.

## Massed Practice Reshuffling Algorithm

### Replaces the current delay-based system

The current massed practice uses delay counters (`delay` field on queue items, `_pop_next()` finding the first item with `delay <= 0`, `_decrement_delays()` after each review). This is replaced with direct positional insertion into a list. No delay counters needed.

Ordered practice is unchanged — ring buffer, no reshuffling.

### On fail

Card is inserted at position 1 (immediately after the next card in the queue).

### On pass

Track `pass_count` per card in the session (in-memory `dict[int, int]` mapping `card_id → count`, not persisted).

**For exact-answer cards:** `pass_count` increments on every correct answer.

**For masking cards:** `pass_count` increments only on type-in level passes (virtual level 3). Masking-level passes (levels 0→1, 1→2, graduation) advance the masking level and requeue using the 1st-pass spacing range, but do not increment `pass_count`.

### Spacing ranges

| Pass # | Range | Notes |
|--------|-------|-------|
| 1st | 2–4 | Light spacing, just saw it |
| 2nd | 4–8 | Building recall |
| 3rd+ | 8–12 | Solidifying and maintenance |

Masking-level passes (not yet at type-in) always use the 1st-pass range (2–4).

Position is `random.randint(low, high)`, clamped to `len(queue)` if fewer cards remain than the upper bound.

### Rationale for randomization

Fixed spacing (3/6/9) creates predictable card order patterns, which can lead to context-dependent recall — remembering the answer because of which card came before, not because the fact is encoded. Randomized ranges prevent this while maintaining approximately increasing intervals for successive passes.

## Numeric-Aware Answer Matching

At review time, when checking an exact-answer card:

1. Strip whitespace from both typed and stored answer
2. Try parsing both as numbers:
   - Remove commas (thousands separators): "1,234" → "1234"
   - Parse as float
3. If both parse as numbers: compare numerically (`float(typed) == float(stored)`)
4. If either doesn't parse: compare as case-insensitive strings

Examples:
- "6.20" matches "6.2" (both parse to 6.2)
- "1234" matches "1,234" (both parse to 1234.0)
- "$6.2" fails against "6.2" (dollar sign prevents numeric parse, string comparison fails)
- "yes" matches "Yes" (case-insensitive string fallback)

No tolerance — the number must be exact. This lives in a function in `text_scoring.py` alongside the existing token-level comparison.

## Per-Card Pass Counter

### Tracking

In-memory `dict[int, int]` mapping `card_id → pass_count` for the current session. Initialized empty. Incremented on each qualifying pass:
- Masking cards: pass at type-in level (virtual level 3)
- Exact-answer cards: any correct answer

### Display

Shown on the answer screen in a consistent position (header or footer bar area). Format: `Pass 2`, `Pass 3`, etc. Cards with 0 passes show nothing.

At 3+ passes, the counter displays in green to signal the card has met the minimum encoding threshold.

### No functional effect

The pass counter is purely informational. It does not affect reshuffling, queue removal, or any other behavior. The user decides when to stop drilling — the counter just helps track progress.

## TUI Branching

### Review screen (showing the card)

Based on `card_type` of the current queue item:

- **`masking`**: show masked text at current level, or blank input for type-in level. Same as today.
- **`exact`**: show the question text, blank input for answer. No masking phase.

### Answer evaluation

- **`masking` at type-in level**: token-level Levenshtein comparison (`text_scoring.py`), colored diff display, user presses Space/Enter (pass) or f (fail). Same as today.
- **`exact`**: numeric-aware match. If correct → auto-pass (no user judgment). If wrong → auto-fail. No manual pass/fail decision.

### Answer screen display

Both card types show:
- The correct answer
- Per-card pass counter (if > 0)

Type-specific:
- **`masking` type-in**: colored token diff (green/yellow/red) as today
- **`exact` wrong answer**: "Expected: X" / "You typed: Y"
- **`exact` correct answer**: confirmation display

### Ordered practice

No changes to ordered practice logic. The ring buffer behavior is card-type-agnostic. Card type only affects rendering and answer checking.

## What's Not In Scope

- **Anki `.apkg` import** — future work, CSV covers initial needs
- **Anki `.apkg` export of generation cards** — future work
- **Changes to global review lifecycle** (masking → graduation → FSRS recall) — only massed/ordered practice is affected
- **Catalog changes** — exact-answer cards use the same deck/topic/source/section hierarchy, catalog works as-is
