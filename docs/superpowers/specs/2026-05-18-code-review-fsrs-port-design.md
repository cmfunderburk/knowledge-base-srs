# Code-Review FSRS Port (Anki-Style Learning Steps)

**Status:** Approved for implementation
**Date:** 2026-05-18

## Problem

`code_review` currently schedules exercises with a 5-box Leitner system (intervals 1/2/4/8/16 days, grade 1=Again resets to box 1). The first interval is too long: when an exercise is failed, the next attempt is a full day away, even though the solution is fresh and the user wants to re-encode the pattern immediately.

The user already runs an Anki configuration with FSRS + learning/lapse steps:

- New cards: learning steps `1m, 10m, 4h, 12h`
- Lapses: relearning steps `30m, 4h`
- FSRS desired retention: `0.95`

The goal is to port this exact configuration to `code_review`, replacing Leitner. A side-benefit is that the SRS module's existing `srs/fsrs.py` (standard FSRS v6, 4-button) can be reused for the core math; only the learning/relearning state machine is new.

## Non-goals

- **No** Anki addon. Possibly a future project; this design keeps the scheduler core and exercise harness decoupled from the TUI so that an eventual addon could reuse `runner.py` as a library, but no addon-specific work is in scope.
- **No** per-deck / per-exercise configuration. Steps and retention live as module constants.
- **No** preservation of existing scheduling state. The current DB has 4 exercises (all box 1) and 6 review-log rows. Migration is a clean wipe and reset to learning step 0.
- **No** changes to `runner.py` (the editor → pytest → diff harness).

## Approach

Three options were considered:

- **A. Reuse `srs/fsrs.py`, write new state machine in `code_review/scheduler.py`** — chosen
- B. Vendor a copy of `fsrs.py` into `code_review/` — rejected (drift, duplication)
- C. Adopt the `fsrs` PyPI package — rejected (new dep, inconsistent with SRS module)

The `srs/fsrs.py` module is already pure functional math (initial/recall/lapse/short-term stability, difficulty update). One small change parameterizes `compute_interval(stability, desired_retention=DESIRED_RETENTION)` so `code_review` can request retention 0.95 while the SRS module continues at 0.9.

## State machine

A card lives in one of three phases. All transitions are pure functions over `(phase, step_index, stability, difficulty, grade, now) → new state`.

```
                ┌─────────────┐
                │  LEARNING   │   steps = [1m, 10m, 4h, 12h]
                │  step 0..3  │
                └─────────────┘
                  │     ▲
        Good past │     │ Again (from REVIEW)
       last step  │     │
         or Easy  ▼     │
                ┌─────────────┐
                │   REVIEW    │   FSRS-scheduled (stability, difficulty)
                │             │   interval via compute_interval(s, 0.95)
                └─────────────┘
                  │     ▲
            Again │     │ Good past last step or Easy
                  ▼     │
                ┌─────────────┐
                │ RELEARNING  │   steps = [30m, 4h]
                │  step 0..1  │
                └─────────────┘
```

### Grade semantics by phase

| Phase | Again | Hard | Good | Easy |
|---|---|---|---|---|
| LEARNING | step=0, due=+1m (first learning step) | repeat current step | advance; past last step → graduate to REVIEW | graduate to REVIEW immediately |
| REVIEW | → RELEARNING step 0, store `lapse_stability(...)` on card, due=+30m | FSRS `recall_stability` with Hard modifier | FSRS `recall_stability` | FSRS `recall_stability` with Easy modifier |
| RELEARNING | reset to step 0, due=+30m | repeat current step | advance; past last step → return to REVIEW with the lapse-time stability | return to REVIEW immediately with the lapse-time stability |

**Graduation seeding** (LEARNING → REVIEW): `stability = initial_stability(grade)`, `difficulty = initial_difficulty(grade)`. Good at graduation → ~3.1d stability; Easy → ~15.5d.

**Lapse seeding** (REVIEW → RELEARNING): `lapse_stability(prior_s, prior_d, retrievability)` is computed at lapse time and stored on the card. That stability is used when the card completes relearning and returns to REVIEW. `difficulty` updates via `update_difficulty(d, Again)` at lapse.

**Edge cases in semantics:**

- Hard in LEARNING / RELEARNING repeats the current step (does not advance). Anki's special "average of step 0 and 1 on the very first step" case is intentionally not replicated — keeps the state machine uniform.
- Again in RELEARNING resets to relearning step 0 (does not drop back to LEARNING).
- Easy in LEARNING graduates with EASY-seeded stability regardless of which step the card is on.

### Learn-ahead window

20 minutes (Anki's `collapseTime` default). The due query returns anything with `due <= now + 20m`, so a card with a 10m step shows up early if the rest of the queue is clear.

## Components & files

**New:**

- `src/knowledge_base/code_review/scheduler.py`
  - `Phase(IntEnum)`: LEARNING=1, REVIEW=2, RELEARNING=3
  - Module constants:
    - `LEARNING_STEPS_SEC = [60, 600, 14400, 43200]`
    - `RELEARNING_STEPS_SEC = [1800, 14400]`
    - `DESIRED_RETENTION = 0.95`
    - `LEARN_AHEAD_SEC = 1200`
  - `@dataclass CardState`: `phase, step_index, stability, difficulty, reps, last_review, due`
  - `@dataclass ScheduleResult`: same shape; returned by `schedule()`
  - `schedule(state: CardState, grade: Grade, now: datetime) -> ScheduleResult` — single entry point; dispatches on `state.phase`
  - `initial_state(now: datetime) -> CardState` — fresh card: phase=LEARNING, step_index=0, stability=0, difficulty=0, reps=0, last_review=None, due=now
- `tests/code_review/test_scheduler.py` — replaces `test_leitner.py`

**Modified:**

- `src/knowledge_base/srs/fsrs.py`
  - `compute_interval(stability, desired_retention: float = DESIRED_RETENTION)` — accept retention as kwarg. Module constant unchanged; default preserves existing behavior for all SRS-module callers.
- `src/knowledge_base/code_review/db.py`
  - `code_exercises` schema: drop `box`; add `phase INTEGER NOT NULL DEFAULT 1`, `step_index INTEGER NOT NULL DEFAULT 0`, `stability REAL NOT NULL DEFAULT 0`, `difficulty REAL NOT NULL DEFAULT 0`. Keep `slug`, `title`, `path`, `source`, `last_review`, `due`, `reps`, `added`.
  - `code_review_log` schema: replace `prior_box`/`new_box` with `prior_phase`, `new_phase`, `prior_stability`, `new_stability`, `prior_difficulty`, `new_difficulty`. Keep `review_id`, `exercise_id`, `timestamp`, `grade`, `elapsed_days`.
  - On `init_db`: detect old `box` column → drop both tables → recreate. Record purged slugs in existing `LAST_MIGRATION_PURGE` so the TUI can surface a one-time banner.
  - `record_grade(conn, exercise_id, new_state, prior_state, grade, elapsed_days, now)` — atomic update + log.
  - `get_due_exercises(conn, as_of)` — query `due <= ?`; caller passes `now + LEARN_AHEAD_SEC`.
- `src/knowledge_base/code_review/tui.py`
  - `ExerciseListScreen`: pass `now + 20m` to due query. Format display column as "due in 8m" / "due in 3h" / "due 2026-05-20" depending on horizon. Refresh on `on_resume` from `ReviewScreen` (no timer). When list is empty but learning cards exist beyond learn-ahead, show footer: "X cards in learning, next due in Ym".
  - `ReviewScreen`: same problem → editor → pytest → diff → grade flow. Grade callback: `prior = db.get_exercise_by_slug(slug)`, `new = scheduler.schedule(prior, grade, now)`, `db.record_grade(...)`.
- `CLAUDE.md` — update Quick Reference and "Key Constraints — Code Review" sections; replace Leitner description with FSRS-with-learning-steps description.

**Deleted:**

- `src/knowledge_base/code_review/leitner.py`
- `tests/code_review/test_leitner.py`

**No new dependencies.**

## Data flow

**Cold start (first run after migration):**

1. `init_db()` detects old `box` column → drops & recreates tables.
2. `sync_exercises_from_disk()` registers each exercise dir with `initial_state(now)`.
3. `ExerciseListScreen` queries `due <= now + 20m` → all rows visible.

**Per-review cycle:**

```
TUI list screen
    │  user selects exercise
    ▼
ReviewScreen.on_mount
    │  show problem.md
    │  launch $EDITOR
    │  on editor close: write submission.py, run pytest, compute diff
    ▼
Grade buttons (Again/Hard/Good/Easy)
    │  user grades
    ▼
prior_state = db.get_exercise_by_slug(slug)  → CardState
new_state   = scheduler.schedule(prior_state, grade, now)
db.record_grade(conn, exercise_id, new_state, prior_state, grade, elapsed_days, now)
    │
    ▼
pop ReviewScreen → ExerciseListScreen.on_resume
    │  re-query due list with now + 20m
    ▼
loop
```

**Time semantics:**

- All `due` and `last_review` are ISO-8601 UTC timestamps.
- `elapsed_days = (now - last_review) / 86400.0` as a float. `last_review` NULL (reps=0) → not used; LEARNING phase handles first review without invoking FSRS.

**In-session learning queue:** the DB is the queue. No separate in-memory data structure. List screen re-queries on every resume.

## Error handling

**Hard-fail invariants** (`ValueError`, matching current style):

- Unknown phase or grade
- `step_index` out of bounds for the phase's step list
- Phase / stability mismatch on read (e.g., REVIEW with stability=0)

**Edge cases:**

- **Clock skew** (`now < last_review`): floor `elapsed_days` to 0. Don't raise.
- **First review** (`reps=0`): `last_review` is NULL; LEARNING phase doesn't use FSRS, so no issue. On graduation, FSRS sees the seeded stability/difficulty as the prior state.
- **User quits mid-review**: no DB write happened; card stays in prior state. Already true today.
- **Exercise deleted from disk**: `sync_exercises_from_disk` doesn't delete rows. Pruning out of scope.
- **DST / timezone**: all times UTC, no DST.

**Explicitly not handled:**

- Concurrent TUI sessions on the same DB (single-user assumption, same as today).
- Hand-edited / corrupted FSRS state: hard-fail on read with a clear error rather than silently repair.

## Testing

`tests/code_review/test_scheduler.py` (new):

- For each phase × each grade: assert resulting `phase`, `step_index`, `due` delta, `stability`, `difficulty`.
- Graduation: Good at last LEARNING step → REVIEW with `stability == initial_stability(Grade.GOOD)`, `difficulty == initial_difficulty(Grade.GOOD)`.
- Easy bypass: Easy at LEARNING step 0 → REVIEW with EASY seeding.
- Lapse round-trip: REVIEW → Again → RELEARNING → Good → Good → back in REVIEW with stability matching the `lapse_stability(...)` computed at lapse time.
- Hard repeats current step (LEARNING and RELEARNING).
- Again in RELEARNING resets to step 0 (does not drop to LEARNING).
- Clock skew: `now < last_review` → `elapsed_days` floored to 0.
- Retention wiring: REVIEW-phase Good produces an interval matching `compute_interval(s, 0.95)`, strictly less than the 0.9 case.

`tests/code_review/test_db.py` (updated):

- Migration: open a DB with old `box`-schema → purges + recreates with new schema; `LAST_MIGRATION_PURGE` populated.
- `record_grade` atomicity: rollback on exception leaves both tables unchanged.
- `get_due_exercises` with learn-ahead window: near-due learning cards included; far-future review cards excluded.

`tests/code_review/test_tui.py` (updated):

- "due in 8m" / "due in 3h" / "due 2026-05-20" formatter across three horizons.
- List refresh on `on_resume` brings back a card whose 1m step just elapsed.
- Empty-list footer renders correctly when learning cards exist beyond learn-ahead.

`tests/srs/test_fsrs.py` (existing, augmented):

- `compute_interval(s, desired_retention=0.95)` returns strictly smaller interval than `compute_interval(s)` — guards the parameterization.

`tests/code_review/test_runner.py` (existing): untouched.

## Open questions

None.
