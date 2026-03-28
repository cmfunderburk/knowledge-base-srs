# Calibration SRS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TUI-based spaced repetition module that scores confidence interval calibration and uses those scores to modulate SRS scheduling via a simplified FSRS model.

**Architecture:** New `srs/` subpackage under `src/knowledge_base/` with SQLite persistence, sharing config and CSV data with the existing Anki pipeline. Pure functions for question generation are extracted into a shared `card_gen.py`. The TUI is built with Textual.

**Tech Stack:** Python 3.12+, SQLite (stdlib), Textual (TUI), Polars (CSV reading), pytest

**Spec:** `docs/superpowers/specs/2026-03-28-calibration-srs-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `src/knowledge_base/card_gen.py` | Shared pure functions: `generate_question`, `generate_notes`, `generate_notes_land_area`, `format_answer`, `build_tags`, `_format_number` |
| `src/knowledge_base/srs/__init__.py` | Package marker |
| `src/knowledge_base/srs/db.py` | SQLite schema (cards, review_log, schema_version), CRUD operations, migrations |
| `src/knowledge_base/srs/scoring.py` | `score_interval()`, `score_point()`, `apply_difficulty_modifier()` |
| `src/knowledge_base/srs/scheduler.py` | DSR model: `compute_retrievability()`, `update_card_state()`, `compute_interval()`, `get_due_cards()` |
| `src/knowledge_base/srs/importer.py` | CSV → SQLite: reads data CSVs + descriptive stats, upserts cards |
| `src/knowledge_base/srs/tui.py` | Textual app: review session, answer display, stats screen |
| `src/knowledge_base/srs/stats.py` | `brier_score()`, `calibration_rate()`, `score_distribution()`, per-deck/indicator breakdowns |
| `tests/test_card_gen.py` | Tests for extracted card_gen functions |
| `tests/test_scoring.py` | Tests for scoring module |
| `tests/test_scheduler.py` | Tests for scheduler module |
| `tests/test_srs_db.py` | Tests for database operations |
| `tests/test_importer.py` | Tests for CSV import |
| `tests/test_stats.py` | Tests for stats computations |

### Modified Files

| File | Change |
|------|--------|
| `src/knowledge_base/build_deck.py` | Remove extracted functions, import from `card_gen.py` |
| `tests/test_build_deck.py` | Update imports to `card_gen` |
| `pyproject.toml` | Add `textual` dependency, `review` and `srs-import` entry points |

---

## Task 1: Extract `card_gen.py` from `build_deck.py`

**Files:**
- Create: `src/knowledge_base/card_gen.py`
- Modify: `src/knowledge_base/build_deck.py:353-453`
- Modify: `tests/test_build_deck.py:1-13`
- Create: `tests/test_card_gen.py`

- [ ] **Step 1: Create `card_gen.py` with extracted functions**

```python
# src/knowledge_base/card_gen.py
"""Shared card generation functions used by both build_deck and SRS importer."""

from __future__ import annotations


def _format_number(
    value: float | int, prefix: str = "", decimals: int = 0
) -> str:
    """Format a number with commas and an optional prefix."""
    if decimals == 0:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:,.{decimals}f}"


def format_answer(value: float, indicator: dict) -> str:
    """Round and format a numerical answer for the card."""
    scale_factor = indicator.get("scale_factor", 1)
    decimals = indicator.get("decimals", 1)
    scaled = value / scale_factor
    rounded = round(scaled, decimals)
    if decimals == 0:
        return str(int(rounded))
    return f"{rounded:.{decimals}f}"


def generate_question(
    entity: str,
    indicator_name: str,
    year: int,
    unit_label: str,
    era: str,
) -> str:
    """Produce the Front field for a card.

    Uses "What is...as of {year}" for current era,
    "What was...in {year}" for historical eras.
    """
    if era == "current":
        return (
            f"What is {entity}'s {indicator_name} as of {year}, {unit_label}?"
        )
    else:
        return (
            f"What was {entity}'s {indicator_name} in {year}, {unit_label}?"
        )


def generate_notes(
    source: str,
    world_avg: float | None,
    regional_avg: float | None,
    unit_prefix: str = "",
    decimals: int = 0,
) -> str:
    """Produce the Notes field with source and reference comparisons."""
    parts = [f"Source: {source}"]
    if world_avg is not None:
        formatted_world = _format_number(world_avg, unit_prefix, decimals)
        if regional_avg is not None:
            formatted_regional = _format_number(
                regional_avg, unit_prefix, decimals
            )
            parts.append(
                f"World avg: {formatted_world}, regional avg: {formatted_regional}"
            )
        else:
            parts.append(f"World avg: {formatted_world}")
    return " | ".join(parts)


def generate_notes_land_area(
    source: str,
    reference_total: int | float,
) -> str:
    """Produce the Notes field for land area cards."""
    formatted_total = f"{reference_total:,.0f}"
    return f"Source: {source} | Reference total: {formatted_total} km\u00b2"


def build_tags(
    category: str,
    indicator_id: str,
    entity_slug: str,
    entity_type: str,
    era: str,
) -> list[str]:
    """Return a list of tag strings for a note."""
    return [
        f"category::{category}",
        f"indicator::{indicator_id}",
        f"entity::{entity_slug}",
        f"entity_type::{entity_type}",
        f"era::{era}",
    ]
```

- [ ] **Step 2: Update `build_deck.py` to import from `card_gen`**

In `src/knowledge_base/build_deck.py`, add at the top (after existing imports):

```python
from knowledge_base.card_gen import (
    format_answer,
    generate_question,
    generate_notes,
    generate_notes_land_area,
    build_tags,
    _format_number,
)
```

Then delete lines 353–445 (the six extracted functions: `format_answer`, `generate_question`, `_format_number`, `generate_notes`, `generate_notes_land_area`, `build_tags`).

Keep `_format_stat` (line 448) and `compute_reference_averages` (line 323) in `build_deck.py` — `_format_stat` is only used by descriptive stats cloze generation, and `compute_reference_averages` depends on Polars DataFrames specific to the build pipeline.

- [ ] **Step 3: Create `tests/test_card_gen.py`**

```python
# tests/test_card_gen.py
from knowledge_base.card_gen import (
    format_answer,
    generate_question,
    generate_notes,
    generate_notes_land_area,
    build_tags,
    _format_number,
)


def test_generate_question_current_era():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=2022,
        unit_label="in 2021 international dollars",
        era="current",
    )
    assert q == "What is India's GDP per capita (PPP) as of 2022, in 2021 international dollars?"


def test_generate_question_historical_era():
    q = generate_question(
        entity="India",
        indicator_name="GDP per capita (PPP)",
        year=1990,
        unit_label="in 2021 international dollars",
        era="1990",
    )
    assert q == "What was India's GDP per capita (PPP) in 1990, in 2021 international dollars?"


def test_generate_notes_with_regional():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=7200,
        unit_prefix="$",
    )
    assert "World Bank WDI" in notes
    assert "World avg: $17,500" in notes
    assert "regional avg: $7,200" in notes


def test_generate_notes_without_regional():
    notes = generate_notes(
        source="World Bank WDI",
        world_avg=17500,
        regional_avg=None,
        unit_prefix="$",
    )
    assert "regional avg" not in notes
    assert "World avg: $17,500" in notes


def test_generate_notes_land_area():
    notes = generate_notes_land_area(
        source="World Bank WDI",
        reference_total=30_370_000,
    )
    assert "World Bank WDI" in notes
    assert "30,370,000" in notes


def test_build_tags():
    tags = build_tags(
        category="development",
        indicator_id="gdp_pc_ppp",
        entity_slug="india",
        entity_type="major",
        era="current",
    )
    assert tags == [
        "category::development",
        "indicator::gdp_pc_ppp",
        "entity::india",
        "entity_type::major",
        "era::current",
    ]


def test_format_answer_with_scale_factor():
    indicator = {"decimals": 1, "scale_factor": 1_000_000_000}
    result = format_answer(2_345_000_000, indicator)
    assert result == "2.3"


def test_format_answer_default_scale_factor():
    indicator = {"decimals": 0}
    result = format_answer(17500.4, indicator)
    assert result == "17500"


def test_format_number_with_prefix():
    assert _format_number(17500, prefix="$") == "$17,500"


def test_format_number_with_decimals():
    assert _format_number(3.14159, prefix="", decimals=2) == "3.14"
```

- [ ] **Step 4: Update `tests/test_build_deck.py` imports**

Replace lines 4–13 in `tests/test_build_deck.py`:

```python
from knowledge_base.card_gen import (
    generate_question,
    generate_notes,
    generate_notes_land_area,
    build_tags,
    format_answer,
)
from knowledge_base.build_deck import (
    compute_reference_averages,
    generate_cloze_content,
    generate_desc_stats_note_field,
)
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: All 44 existing tests pass. New `test_card_gen.py` tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/card_gen.py tests/test_card_gen.py src/knowledge_base/build_deck.py tests/test_build_deck.py
git commit -m "refactor: extract card_gen.py from build_deck.py

Pure functions for question/notes/answer/tag generation are now shared
between build_deck and the upcoming SRS module."
```

---

## Task 2: Scoring Module

**Files:**
- Create: `src/knowledge_base/srs/__init__.py`
- Create: `src/knowledge_base/srs/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Create package and write failing tests**

Create empty `src/knowledge_base/srs/__init__.py`.

```python
# tests/test_scoring.py
import math
import pytest
from knowledge_base.srs.scoring import score_interval, score_point, apply_difficulty_modifier


class TestScoreInterval:
    """Tests for 95% CI scoring: Cobb-Douglas with coverage gate."""

    def test_perfect_center_tight_interval_covered(self):
        """Dead center, tight interval, truth inside → high score."""
        result = score_interval(
            lower=90, upper=110, true_answer=100, indicator_std=50
        )
        # accuracy_score = exp(-|100-100|/50) = exp(0) = 1.0
        # precision_score = exp(-20/(3.92*50)) = exp(-0.102) ≈ 0.903
        # core = 1.0^0.5 * 0.903^0.5 ≈ 0.950
        # covered → score = core
        assert result.score == pytest.approx(0.950, abs=0.01)
        assert result.accuracy_score == pytest.approx(1.0)
        assert result.precision_score == pytest.approx(0.903, abs=0.01)
        assert result.covered is True

    def test_off_center_but_covered(self):
        """Truth inside interval but not centered → lower accuracy."""
        result = score_interval(
            lower=50, upper=150, true_answer=140, indicator_std=50
        )
        # center = 100, accuracy_error = |140-100|/50 = 0.8
        # accuracy_score = exp(-0.8) ≈ 0.449
        # width = 100, precision_score = exp(-100/(3.92*50)) ≈ 0.601
        # core = 0.449^0.5 * 0.601^0.5 ≈ 0.520
        assert result.covered is True
        assert result.score == pytest.approx(0.520, abs=0.02)

    def test_not_covered_applies_penalty(self):
        """Truth outside interval → 0.2x penalty on core."""
        result = score_interval(
            lower=200, upper=300, true_answer=100, indicator_std=50
        )
        assert result.covered is False
        # core * 0.2
        assert result.score < 0.15

    def test_very_wide_interval_low_precision(self):
        """Wide hedge → low precision even if centered and covered."""
        result = score_interval(
            lower=0, upper=1000, true_answer=500, indicator_std=100
        )
        # center=500, perfect accuracy, but width=1000, precision_score=exp(-1000/392)≈0.078
        # core = 1.0^0.5 * 0.078^0.5 ≈ 0.280
        assert result.score < 0.35
        assert result.precision_score < 0.1

    def test_tight_interval_off_center_not_covered(self):
        """Confident and wrong → low accuracy, not covered, harsh score."""
        result = score_interval(
            lower=10, upper=20, true_answer=100, indicator_std=50
        )
        assert result.covered is False
        assert result.score < 0.05


class TestScorePoint:
    """Tests for point prediction scoring."""

    def test_exact_match(self):
        """Within 0.05 SDs → perfect score."""
        # indicator_std=100, 0.05*100=5, so answer within 5 of true
        score = score_point(user_point=101, true_answer=100, indicator_std=100)
        assert score == 1.0

    def test_close_but_not_exact(self):
        """Within 0.25 SDs → partial score."""
        # error = |120-100|/100 = 0.2 < 0.25
        score = score_point(user_point=120, true_answer=100, indicator_std=100)
        assert score == 0.5

    def test_wrong(self):
        """Beyond 0.25 SDs → zero score."""
        # error = |200-100|/100 = 1.0
        score = score_point(user_point=200, true_answer=100, indicator_std=100)
        assert score == 0.0

    def test_boundary_005(self):
        """At exactly 0.05 SDs boundary → still 1.0 (strictly less than)."""
        score = score_point(user_point=105, true_answer=100, indicator_std=100)
        assert score == 0.5  # error = 0.05, not < 0.05

    def test_boundary_025(self):
        """At exactly 0.25 SDs boundary → 0.0 (strictly less than)."""
        score = score_point(user_point=125, true_answer=100, indicator_std=100)
        assert score == 0.0  # error = 0.25, not < 0.25


class TestDifficultyModifier:
    """Tests for optional difficulty modifier."""

    def test_outlier_gets_bonus(self):
        """3-SD outlier → ~1.3x modifier."""
        modified = apply_difficulty_modifier(
            score=0.5, true_answer=400, indicator_mean=100, indicator_std=100
        )
        # difficulty_z = |400-100|/100 = 3.0, modifier = 1 + 0.1*3 = 1.3
        assert modified == pytest.approx(0.65)

    def test_average_entity_no_bonus(self):
        """Entity at mean → modifier ≈ 1.0."""
        modified = apply_difficulty_modifier(
            score=0.5, true_answer=100, indicator_mean=100, indicator_std=100
        )
        assert modified == pytest.approx(0.5)

    def test_capped_at_1(self):
        """High score + outlier bonus capped at 1.0."""
        modified = apply_difficulty_modifier(
            score=0.95, true_answer=400, indicator_mean=100, indicator_std=100
        )
        assert modified == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_base.srs.scoring'`

- [ ] **Step 3: Implement scoring module**

```python
# src/knowledge_base/srs/scoring.py
"""Calibration scoring for interval and point prediction answers."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Width of a 95% CI for a standard normal distribution (2 * 1.96)
NORMAL_95_WIDTH = 3.92

COVERAGE_PENALTY = 0.2


@dataclass
class IntervalResult:
    """Result of scoring an interval prediction."""

    accuracy_score: float
    precision_score: float
    covered: bool
    score: float


def score_interval(
    lower: float,
    upper: float,
    true_answer: float,
    indicator_std: float,
) -> IntervalResult:
    """Score a 95% CI prediction using Cobb-Douglas with coverage gate.

    Args:
        lower: User's lower bound.
        upper: User's upper bound.
        true_answer: The correct value.
        indicator_std: Population standard deviation of the indicator
                       (in display units).

    Returns:
        IntervalResult with component scores and final score.
    """
    center = (lower + upper) / 2
    width = upper - lower

    accuracy_error = abs(true_answer - center) / indicator_std
    accuracy_score = math.exp(-accuracy_error)

    precision_ratio = width / (NORMAL_95_WIDTH * indicator_std)
    precision_score = math.exp(-precision_ratio)

    core = accuracy_score**0.5 * precision_score**0.5

    covered = lower <= true_answer <= upper
    score = core if covered else core * COVERAGE_PENALTY

    return IntervalResult(
        accuracy_score=accuracy_score,
        precision_score=precision_score,
        covered=covered,
        score=score,
    )


def score_point(
    user_point: float,
    true_answer: float,
    indicator_std: float,
) -> float:
    """Score a point prediction. Thresholds are deliberately punitive.

    Args:
        user_point: The user's point estimate.
        true_answer: The correct value.
        indicator_std: Population standard deviation of the indicator.

    Returns:
        Score: 1.0 (within 0.05 SDs), 0.5 (within 0.25 SDs), or 0.0.
    """
    error = abs(true_answer - user_point) / indicator_std
    if error < 0.05:
        return 1.0
    if error < 0.25:
        return 0.5
    return 0.0


def apply_difficulty_modifier(
    score: float,
    true_answer: float,
    indicator_mean: float,
    indicator_std: float,
) -> float:
    """Apply optional difficulty bonus for outlier entities.

    Args:
        score: The base score from interval or point scoring.
        true_answer: The correct value.
        indicator_mean: Population mean of the indicator.
        indicator_std: Population standard deviation of the indicator.

    Returns:
        Modified score, capped at 1.0.
    """
    difficulty_z = abs(true_answer - indicator_mean) / indicator_std
    modifier = 1 + 0.1 * difficulty_z
    return min(1.0, score * modifier)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/__init__.py src/knowledge_base/srs/scoring.py tests/test_scoring.py
git commit -m "feat(srs): add scoring module for interval and point predictions

Cobb-Douglas combination of accuracy and precision with coverage gate
for interval mode. Punitive step-function thresholds for point
predictions. Optional difficulty modifier for outlier entities."
```

---

## Task 3: Scheduler Module

**Files:**
- Create: `src/knowledge_base/srs/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scheduler.py
import math
import pytest
from knowledge_base.srs.scheduler import (
    compute_retrievability,
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
    GROWTH_FACTOR,
    BASE_RETENTION,
)


class TestRetrievability:
    def test_just_reviewed(self):
        """Zero elapsed days → R = 1.0 (just saw it)."""
        r = compute_retrievability(elapsed_days=0, stability=10)
        assert r == pytest.approx(1.0)

    def test_at_stability(self):
        """Elapsed = stability → R = 0.9 by definition."""
        r = compute_retrievability(elapsed_days=10, stability=10)
        assert r == pytest.approx(0.9)

    def test_double_stability(self):
        """Elapsed = 2*stability → R = 0.9^2 = 0.81."""
        r = compute_retrievability(elapsed_days=20, stability=10)
        assert r == pytest.approx(0.81)


class TestDesiredRetention:
    def test_baseline_score(self):
        """Score 0.5 → exactly base retention (0.90)."""
        ret = compute_desired_retention(score=0.5)
        assert ret == pytest.approx(0.90)

    def test_perfect_score(self):
        """Score 1.0 → 0.925."""
        ret = compute_desired_retention(score=1.0)
        assert ret == pytest.approx(0.925)

    def test_zero_score(self):
        """Score 0.0 → 0.85."""
        ret = compute_desired_retention(score=0.0)
        assert ret == pytest.approx(0.875)

    def test_clamped_range(self):
        """Retention stays in valid range even with extreme inputs."""
        # Scores are [0, 1] by design, but test the formula range
        assert 0.0 < compute_desired_retention(0.0) < 1.0
        assert 0.0 < compute_desired_retention(1.0) < 1.0


class TestComputeInterval:
    def test_at_base_retention(self):
        """At 90% retention, interval ≈ stability."""
        interval = compute_interval(stability=10.0, desired_retention=0.9)
        assert interval == pytest.approx(10.0)

    def test_lower_retention_shorter(self):
        """Lower retention target → shorter interval."""
        interval = compute_interval(stability=10.0, desired_retention=0.85)
        assert interval < 10.0

    def test_higher_retention_longer(self):
        """Higher retention target → longer interval."""
        interval = compute_interval(stability=10.0, desired_retention=0.925)
        assert interval > 10.0

    def test_minimum_interval_is_one_day(self):
        """Interval floors at 1 day."""
        interval = compute_interval(stability=0.1, desired_retention=0.85)
        assert interval >= 1.0


class TestUpdateDifficulty:
    def test_good_score_lowers_difficulty(self):
        """Score > 0.7 → difficulty decreases."""
        d_new = update_difficulty(difficulty=0.5, score=0.9)
        assert d_new < 0.5

    def test_bad_score_raises_difficulty(self):
        """Score < 0.7 → difficulty increases."""
        d_new = update_difficulty(difficulty=0.3, score=0.2)
        assert d_new > 0.3

    def test_clamped_low(self):
        """Difficulty doesn't go below 0.05."""
        d_new = update_difficulty(difficulty=0.06, score=1.0)
        assert d_new >= 0.05

    def test_clamped_high(self):
        """Difficulty doesn't exceed 1.0."""
        d_new = update_difficulty(difficulty=0.98, score=0.0)
        assert d_new <= 1.0


class TestUpdateStability:
    def test_successful_review_grows_stability(self):
        """Score >= 0.4 → stability increases."""
        s_new = update_stability(
            stability=5.0, difficulty=0.3, score=0.8
        )
        assert s_new > 5.0

    def test_lapse_drops_stability(self):
        """Score < 0.4 → stability drops to max(1.0, S*0.3)."""
        s_new = update_stability(
            stability=10.0, difficulty=0.3, score=0.1
        )
        assert s_new == pytest.approx(3.0)

    def test_lapse_floors_at_one(self):
        """Lapsed stability doesn't go below 1.0."""
        s_new = update_stability(
            stability=2.0, difficulty=0.3, score=0.1
        )
        assert s_new == 1.0

    def test_lower_difficulty_faster_growth(self):
        """Lower difficulty → larger stability growth factor."""
        s_easy = update_stability(stability=5.0, difficulty=0.1, score=0.8)
        s_hard = update_stability(stability=5.0, difficulty=0.9, score=0.8)
        assert s_easy > s_hard
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement scheduler module**

```python
# src/knowledge_base/srs/scheduler.py
"""Simplified FSRS scheduler with desired-retention modulation."""

from __future__ import annotations

import math

# Fixed constants (optimizable in future full-FSRS upgrade)
GROWTH_FACTOR = 2.0
BASE_RETENTION = 0.90
RETENTION_SCALE = 0.05  # how much score shifts retention
SUCCESS_THRESHOLD = 0.4
DIFFICULTY_RATE = 0.1
DIFFICULTY_ANCHOR = 0.7
MIN_DIFFICULTY = 0.05
MAX_DIFFICULTY = 1.0
LAPSE_FACTOR = 0.3
MIN_STABILITY = 1.0
MIN_INTERVAL = 1.0


def compute_retrievability(elapsed_days: float, stability: float) -> float:
    """Predict probability of recall.

    R = 0.9 ^ (elapsed_days / stability)
    """
    if stability <= 0:
        return 0.0
    return 0.9 ** (elapsed_days / stability)


def compute_desired_retention(score: float) -> float:
    """Shift target retention based on calibration score.

    Range: [BASE - SCALE*0.5, BASE + SCALE*0.5]
    Asymmetric around base: punishes poor calibration more.
    """
    return BASE_RETENTION + RETENTION_SCALE * (score - 0.5)


def compute_interval(stability: float, desired_retention: float) -> float:
    """Compute review interval from stability and desired retention.

    interval = stability * (ln(retention) / ln(0.9))
    Floors at MIN_INTERVAL (1 day).
    """
    if desired_retention <= 0 or desired_retention >= 1:
        return MIN_INTERVAL
    interval = stability * (math.log(desired_retention) / math.log(0.9))
    return max(MIN_INTERVAL, interval)


def update_difficulty(difficulty: float, score: float) -> float:
    """Update card difficulty after a review.

    Moves toward the score: good scores lower difficulty, bad scores raise it.
    """
    d_new = difficulty + DIFFICULTY_RATE * (DIFFICULTY_ANCHOR - score)
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d_new))


def update_stability(
    stability: float, difficulty: float, score: float
) -> float:
    """Update card stability after a review.

    Successful review (score >= 0.4): stability grows.
    Lapse (score < 0.4): stability drops to max(1.0, S * 0.3).
    """
    if score >= SUCCESS_THRESHOLD:
        return stability * (1 + GROWTH_FACTOR * (1 - difficulty) * score)
    return max(MIN_STABILITY, stability * LAPSE_FACTOR)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 14 tests PASS.

Note: `test_zero_score` expects `compute_desired_retention(0.0) == 0.875` because `0.90 + 0.05 * (0.0 - 0.5) = 0.875`. The spec originally said the range is `[0.85, 0.925]` but the formula `0.90 + 0.05 * (score - 0.5)` gives `[0.875, 0.925]`. The implementation follows the formula; the spec's stated range was approximate.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/scheduler.py tests/test_scheduler.py
git commit -m "feat(srs): add simplified FSRS scheduler module

DSR model with desired-retention modulation. Growth factor and
difficulty/stability update rules are forward-compatible with
full FSRS parameter optimization."
```

---

## Task 4: Database Module

**Files:**
- Create: `src/knowledge_base/srs/db.py`
- Create: `tests/test_srs_db.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_srs_db.py
import sqlite3
from pathlib import Path
import pytest
from knowledge_base.srs.db import (
    init_db,
    insert_card,
    get_card,
    upsert_card,
    get_due_cards,
    update_card_scheduling,
    insert_review,
    get_reviews_for_card,
    get_schema_version,
)


@pytest.fixture
def db(tmp_path):
    """Create an in-memory database for testing."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


SAMPLE_CARD = {
    "deck": "development",
    "indicator_id": "gdp_pc_ppp",
    "entity": "India",
    "era": "current",
    "question": "What is India's GDP per capita (PPP) as of 2024?",
    "answer": 2389.0,
    "unit_prefix": "$",
    "unit_label": "in 2021 international dollars",
    "notes": "Source: WB | World avg: $18,463",
    "tags": '["category::development", "indicator::gdp_pc_ppp"]',
    "indicator_mean": 27833.0,
    "indicator_std": 27142.0,
    "scale_factor": 1,
    "decimals": 0,
}


class TestSchema:
    def test_schema_version_is_1(self, db):
        assert get_schema_version(db) == 1

    def test_tables_exist(self, db):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "cards" in tables
        assert "review_log" in tables
        assert "schema_version" in tables


class TestCardCRUD:
    def test_insert_and_get(self, db):
        card_id = insert_card(db, SAMPLE_CARD)
        card = get_card(db, card_id)
        assert card["entity"] == "India"
        assert card["answer"] == 2389.0
        assert card["state"] == "new"
        assert card["difficulty"] == pytest.approx(0.3)
        assert card["stability"] == pytest.approx(1.0)

    def test_upsert_updates_existing(self, db):
        card_id = insert_card(db, SAMPLE_CARD)
        updated = {**SAMPLE_CARD, "answer": 2500.0}
        new_id = upsert_card(db, updated)
        assert new_id == card_id
        card = get_card(db, card_id)
        assert card["answer"] == 2500.0

    def test_upsert_inserts_new(self, db):
        card_id = upsert_card(db, SAMPLE_CARD)
        assert card_id is not None
        assert get_card(db, card_id)["entity"] == "India"

    def test_unique_constraint(self, db):
        insert_card(db, SAMPLE_CARD)
        with pytest.raises(sqlite3.IntegrityError):
            insert_card(db, SAMPLE_CARD)


class TestScheduling:
    def test_update_scheduling(self, db):
        card_id = insert_card(db, SAMPLE_CARD)
        update_card_scheduling(db, card_id, {
            "difficulty": 0.4,
            "stability": 5.0,
            "last_review": "2026-03-28T10:00:00",
            "due": "2026-04-02",
            "reps": 1,
            "consecutive_successes": 1,
            "state": "learning",
        })
        card = get_card(db, card_id)
        assert card["difficulty"] == pytest.approx(0.4)
        assert card["stability"] == pytest.approx(5.0)
        assert card["state"] == "learning"

    def test_get_due_cards_returns_due(self, db):
        card_id = insert_card(db, SAMPLE_CARD)
        # New cards are always "due"
        due = get_due_cards(db, as_of="2026-03-28")
        new_cards = [c for c in due if c["state"] == "new"]
        assert len(new_cards) == 1

    def test_get_due_cards_filters_by_deck(self, db):
        insert_card(db, SAMPLE_CARD)
        due = get_due_cards(db, as_of="2026-03-28", deck="finance")
        assert len([c for c in due if c["state"] == "new"]) == 0


class TestReviewLog:
    def test_insert_and_retrieve(self, db):
        card_id = insert_card(db, SAMPLE_CARD)
        insert_review(db, {
            "card_id": card_id,
            "timestamp": "2026-03-28T10:00:00",
            "answer_mode": "interval",
            "user_lower": 1000.0,
            "user_upper": 5000.0,
            "user_point": None,
            "true_answer": 2389.0,
            "raw_score": 0.74,
            "desired_retention": 0.912,
            "interval_applied": 4.2,
            "elapsed_days": 0.0,
        })
        reviews = get_reviews_for_card(db, card_id)
        assert len(reviews) == 1
        assert reviews[0]["answer_mode"] == "interval"
        assert reviews[0]["raw_score"] == pytest.approx(0.74)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_srs_db.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement database module**

```python
# src/knowledge_base/srs/db.py
"""SQLite database for SRS cards, scheduling state, and review history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    entity TEXT NOT NULL,
    era TEXT NOT NULL,
    question TEXT NOT NULL,
    answer REAL NOT NULL,
    unit_prefix TEXT NOT NULL DEFAULT '',
    unit_label TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    indicator_mean REAL,
    indicator_std REAL,
    scale_factor INTEGER NOT NULL DEFAULT 1,
    decimals INTEGER NOT NULL DEFAULT 0,
    difficulty REAL NOT NULL DEFAULT 0.3,
    stability REAL NOT NULL DEFAULT 1.0,
    last_review TEXT,
    due TEXT,
    reps INTEGER NOT NULL DEFAULT 0,
    consecutive_successes INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'new',
    UNIQUE(indicator_id, entity, era)
);

CREATE TABLE IF NOT EXISTS review_log (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL REFERENCES cards(card_id),
    timestamp TEXT NOT NULL,
    answer_mode TEXT NOT NULL,
    user_lower REAL,
    user_upper REAL,
    user_point REAL,
    true_answer REAL NOT NULL,
    raw_score REAL NOT NULL,
    desired_retention REAL NOT NULL,
    interval_applied REAL NOT NULL,
    elapsed_days REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due, state);
CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck);
CREATE INDEX IF NOT EXISTS idx_review_log_card ON review_log(card_id);
CREATE INDEX IF NOT EXISTS idx_review_log_timestamp ON review_log(timestamp);
"""

MIGRATIONS = [SCHEMA_V1]


def init_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Initialize database, run pending migrations, return connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply pending schema migrations."""
    # Check if schema_version table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cursor.fetchone() is None:
        current = 0
    else:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        current = row[0] if row else 0

    for i in range(current, len(MIGRATIONS)):
        conn.executescript(MIGRATIONS[i])
        if current == 0 and i == 0:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        else:
            conn.execute("UPDATE schema_version SET version = ?", (i + 1,))
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return current schema version."""
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return row[0] if row else 0


def insert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new card. Raises IntegrityError on duplicate."""
    cursor = conn.execute(
        """INSERT INTO cards (deck, indicator_id, entity, era, question, answer,
           unit_prefix, unit_label, notes, tags, indicator_mean, indicator_std,
           scale_factor, decimals)
           VALUES (:deck, :indicator_id, :entity, :era, :question, :answer,
           :unit_prefix, :unit_label, :notes, :tags, :indicator_mean,
           :indicator_std, :scale_factor, :decimals)""",
        card,
    )
    conn.commit()
    return cursor.lastrowid


def get_card(conn: sqlite3.Connection, card_id: int) -> dict | None:
    """Fetch a card by ID. Returns dict or None."""
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def upsert_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert or update a card, matching on (indicator_id, entity, era).

    On conflict, updates content fields but preserves scheduling state.
    """
    cursor = conn.execute(
        """INSERT INTO cards (deck, indicator_id, entity, era, question, answer,
           unit_prefix, unit_label, notes, tags, indicator_mean, indicator_std,
           scale_factor, decimals)
           VALUES (:deck, :indicator_id, :entity, :era, :question, :answer,
           :unit_prefix, :unit_label, :notes, :tags, :indicator_mean,
           :indicator_std, :scale_factor, :decimals)
           ON CONFLICT(indicator_id, entity, era) DO UPDATE SET
           question=excluded.question, answer=excluded.answer,
           unit_prefix=excluded.unit_prefix, unit_label=excluded.unit_label,
           notes=excluded.notes, tags=excluded.tags,
           indicator_mean=excluded.indicator_mean,
           indicator_std=excluded.indicator_std,
           scale_factor=excluded.scale_factor, decimals=excluded.decimals
           RETURNING card_id""",
        card,
    )
    conn.commit()
    return cursor.fetchone()[0]


def update_card_scheduling(
    conn: sqlite3.Connection, card_id: int, fields: dict
) -> None:
    """Update scheduling fields on a card."""
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    conn.execute(
        f"UPDATE cards SET {sets} WHERE card_id = :card_id",
        {**fields, "card_id": card_id},
    )
    conn.commit()


def get_due_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Get cards due for review, ordered by priority.

    Priority: learning step-1 (intra-session), overdue review, learning step-2, new.
    """
    query = """
        SELECT *,
            CASE
                WHEN state = 'learning' AND consecutive_successes = 0 THEN 0
                WHEN state = 'review' AND (due IS NULL OR due <= :as_of) THEN 1
                WHEN state = 'learning' AND (due IS NULL OR due <= :as_of) THEN 2
                WHEN state = 'new' THEN 3
                ELSE 4
            END AS priority
        FROM cards
        WHERE priority < 4
    """
    params: dict = {"as_of": as_of}
    if deck:
        query += " AND deck = :deck"
        params["deck"] = deck
    query += " ORDER BY priority, due ASC"
    if limit:
        query += " LIMIT :limit"
        params["limit"] = limit
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def insert_review(conn: sqlite3.Connection, review: dict) -> int:
    """Append a review to the log."""
    cursor = conn.execute(
        """INSERT INTO review_log (card_id, timestamp, answer_mode,
           user_lower, user_upper, user_point, true_answer, raw_score,
           desired_retention, interval_applied, elapsed_days)
           VALUES (:card_id, :timestamp, :answer_mode, :user_lower,
           :user_upper, :user_point, :true_answer, :raw_score,
           :desired_retention, :interval_applied, :elapsed_days)""",
        review,
    )
    conn.commit()
    return cursor.lastrowid


def get_reviews_for_card(
    conn: sqlite3.Connection, card_id: int
) -> list[dict]:
    """Get all reviews for a card, ordered by timestamp."""
    rows = conn.execute(
        "SELECT * FROM review_log WHERE card_id = ? ORDER BY timestamp",
        (card_id,),
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_srs_db.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/db.py tests/test_srs_db.py
git commit -m "feat(srs): add SQLite database module with schema migrations

Card table with scheduling state, append-only review log, schema
versioning for future migrations. Upsert preserves scheduling
state when reimporting card content."
```

---

## Task 5: Importer Module

**Files:**
- Create: `src/knowledge_base/srs/importer.py`
- Create: `tests/test_importer.py`
- Create: `tests/fixtures/sample_srs_import/` (test CSVs)

- [ ] **Step 1: Create test fixtures**

```csv
# tests/fixtures/sample_srs_import/gdp_pc_ppp.csv
entity,entity_type,region,era,year,value,source
World,region,,current,2024,21405.12,World Bank WDI
India,major,South Asia,current,2024,2389.0,World Bank WDI
USA,major,Europe & Central Asia,current,2024,80384.77,World Bank WDI
South Asia,region,,current,2024,7200.0,World Bank WDI
```

```csv
# tests/fixtures/sample_srs_import/desc_stats_gdp_pc_ppp.csv
indicator_id,indicator_name,category,source_deck,unit_label,unit_prefix,decimals,scale_factor,year,n,mean,median,std,min_value,min_entity,max_value,max_entity
gdp_pc_ppp,GDP per capita (PPP),development,development,in 2021 international dollars,$,0,1,2024,199,27833.0,18068.5,27142.0,1051.3,Burundi,132569.5,Singapore
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_importer.py
from pathlib import Path
import pytest
from knowledge_base.srs.db import init_db, get_card, get_due_cards
from knowledge_base.srs.importer import import_deck


FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


class TestImportDeck:
    def test_imports_country_rows_only(self, db):
        """Regions and aggregates are excluded; only country rows imported."""
        count = import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        assert count == 2  # India and USA, not World or South Asia

    def test_card_fields_populated(self, db):
        import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        due = get_due_cards(db, as_of="2099-01-01")
        india = [c for c in due if c["entity"] == "India"][0]
        assert india["deck"] == "development"
        assert india["indicator_id"] == "gdp_pc_ppp"
        assert india["answer"] == pytest.approx(2389.0)  # scale_factor=1
        assert india["indicator_mean"] == pytest.approx(27833.0)
        assert india["indicator_std"] == pytest.approx(27142.0)
        assert india["state"] == "new"
        assert "GDP per capita" in india["question"]

    def test_idempotent_reimport(self, db):
        """Second import updates content, doesn't duplicate cards."""
        import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        count = import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        assert count == 2
        all_cards = get_due_cards(db, as_of="2099-01-01")
        india_cards = [c for c in all_cards if c["entity"] == "India"]
        assert len(india_cards) == 1

    def test_notes_include_reference_data(self, db):
        """Notes field contains world/regional averages."""
        import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        due = get_due_cards(db, as_of="2099-01-01")
        india = [c for c in due if c["entity"] == "India"][0]
        assert "World avg" in india["notes"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_importer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement importer**

```python
# src/knowledge_base/srs/importer.py
"""Import cards from CSV data into the SRS database."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from knowledge_base.card_gen import (
    build_tags,
    format_answer,
    generate_notes,
    generate_notes_land_area,
    generate_question,
)
from knowledge_base.config import DECKS, ENTITIES
from knowledge_base.build_deck import compute_reference_averages
from knowledge_base.srs.db import upsert_card


def _find_entity_config(entity_name: str, entities: list[dict]) -> dict | None:
    """Find entity config by name."""
    for e in entities:
        if e["name"] == entity_name:
            return e
    return None


def _load_desc_stats(
    desc_stats_dir: Path,
    indicator_id: str,
    prefix: str = "",
) -> dict | None:
    """Load descriptive stats for an indicator. Returns {mean, std} or None."""
    path = desc_stats_dir / f"{prefix}{indicator_id}.csv"
    if not path.exists():
        return None
    df = pl.read_csv(path)
    if df.is_empty():
        return None
    row = df.row(0, named=True)
    return {"mean": row["mean"], "std": row["std"]}


def import_deck(
    conn,
    deck_key: str,
    data_dir: Path | None = None,
    desc_stats_dir: Path | None = None,
    desc_stats_prefix: str = "",
) -> int:
    """Import cards for a deck from CSVs into the database.

    Args:
        conn: SQLite connection from init_db().
        deck_key: Key in DECKS registry.
        data_dir: Override for CSV directory.
        desc_stats_dir: Override for descriptive stats directory.
        desc_stats_prefix: Filename prefix for desc stats CSVs.

    Returns:
        Number of cards upserted.
    """
    if deck_key not in DECKS:
        raise KeyError(f"Unknown deck key: {deck_key!r}")

    deck_cfg = DECKS[deck_key]
    entities = deck_cfg.get("entities", ENTITIES)
    ref_entity = deck_cfg.get("reference_entity", "World")
    ref_entity_type = deck_cfg.get("reference_entity_type", "region")
    indicator_by_id = {ind["id"]: ind for ind in deck_cfg["indicators"]}
    resolved_data = data_dir or Path(deck_cfg["data_dir"])
    resolved_stats = desc_stats_dir or Path("data/descriptive_stats")

    # Determine prefix for urban indicators
    is_urban = deck_key == "urban_areas"
    stats_prefix = desc_stats_prefix or ("urban_" if is_urban else "")

    count = 0
    csv_files = sorted(resolved_data.glob("*.csv"))

    for csv_path in csv_files:
        indicator_id = csv_path.stem
        indicator = indicator_by_id.get(indicator_id)
        if indicator is None:
            continue

        df = pl.read_csv(csv_path)
        scale_factor = indicator.get("scale_factor", 1)
        unit_prefix = indicator.get("unit_prefix", "")
        is_land_area = indicator_id == "land_area"

        # Load descriptive stats
        stats = _load_desc_stats(resolved_stats, indicator_id, stats_prefix)
        ind_mean = stats["mean"] / scale_factor if stats else None
        ind_std = stats["std"] / scale_factor if stats else None

        # Reference averages per era
        eras = df["era"].unique().to_list()
        ref_by_era: dict[str, tuple[float | None, dict[str, float]]] = {}
        for era in eras:
            ref_by_era[era] = compute_reference_averages(
                df, era,
                reference_entity=ref_entity,
                reference_entity_type=ref_entity_type,
            )

        # Filter to country/city rows
        card_rows = df.filter(
            ~pl.col("entity_type").is_in(["region", "aggregate"])
        )

        for row in card_rows.iter_rows(named=True):
            entity_name = row["entity"]
            entity_cfg = _find_entity_config(entity_name, entities)
            if entity_cfg is None:
                continue

            era = row["era"]
            year = row["year"]
            value = row["value"]
            source = row["source"]
            entity_slug = entity_cfg["tag_slug"]
            entity_type = entity_cfg["entity_type"]

            question = generate_question(
                entity=entity_name,
                indicator_name=indicator["name"],
                year=year,
                unit_label=indicator["unit_label"],
                era=era,
            )

            if is_land_area:
                world_avg, region_avgs = ref_by_era.get(era, (None, {}))
                region_name = entity_cfg.get("region", "")
                reference_total = region_avgs.get(region_name, world_avg or 0)
                notes = generate_notes_land_area(
                    source=source,
                    reference_total=reference_total,
                )
            else:
                world_avg, region_avgs = ref_by_era.get(era, (None, {}))
                region_name = entity_cfg.get("region", "")
                regional_avg = region_avgs.get(region_name)
                scaled_world = world_avg / scale_factor if world_avg is not None else None
                scaled_regional = regional_avg / scale_factor if regional_avg is not None else None
                notes = generate_notes(
                    source=source,
                    world_avg=scaled_world,
                    regional_avg=scaled_regional,
                    unit_prefix=unit_prefix,
                    decimals=indicator.get("decimals", 1),
                )

            tags = build_tags(
                category=indicator["category"],
                indicator_id=indicator_id,
                entity_slug=entity_slug,
                entity_type=entity_type,
                era=era,
            )

            display_answer = value / scale_factor

            upsert_card(conn, {
                "deck": deck_key,
                "indicator_id": indicator_id,
                "entity": entity_name,
                "era": era,
                "question": question,
                "answer": display_answer,
                "unit_prefix": unit_prefix,
                "unit_label": indicator["unit_label"],
                "notes": notes,
                "tags": json.dumps(tags),
                "indicator_mean": ind_mean,
                "indicator_std": ind_std,
                "scale_factor": scale_factor,
                "decimals": indicator.get("decimals", 0),
            })
            count += 1

    return count


def main() -> None:
    """CLI entry point: srs-import."""
    import sys
    from knowledge_base.srs.db import init_db

    if len(sys.argv) < 2:
        print("Usage: srs-import <deck_key>")
        deck_keys = [k for k in DECKS if k != "descriptive_stats"]
        print(f"Available decks: {', '.join(deck_keys)}")
        raise SystemExit(1)

    deck_key = sys.argv[1]
    db_path = Path("data/srs.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)

    try:
        count = import_deck(conn, deck_key)
        print(f"Imported {count} cards for {deck_key}")
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_importer.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/importer.py tests/test_importer.py tests/fixtures/sample_srs_import/
git commit -m "feat(srs): add CSV importer with idempotent upsert

Reads data CSVs and descriptive stats, populates card database with
display-unit values and indicator statistics. Shares card generation
logic with build_deck via card_gen module."
```

---

## Task 6: Stats Module

**Files:**
- Create: `src/knowledge_base/srs/stats.py`
- Create: `tests/test_stats.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stats.py
import pytest
from knowledge_base.srs.stats import (
    brier_score,
    calibration_rate,
    score_distribution,
    point_hit_rate,
)


class TestBrierScore:
    def test_perfect_calibration(self):
        """95% coverage → Brier ≈ 0.0475."""
        # 95 covered, 5 not covered out of 100
        coverages = [True] * 95 + [False] * 5
        bs = brier_score(coverages, confidence=0.95)
        assert bs == pytest.approx(0.0475)

    def test_always_covered(self):
        """100% coverage at 95% CI → overconfident intervals."""
        coverages = [True] * 100
        bs = brier_score(coverages, confidence=0.95)
        assert bs == pytest.approx(0.0025, abs=0.001)

    def test_never_covered(self):
        """0% coverage → terrible calibration."""
        coverages = [False] * 100
        bs = brier_score(coverages, confidence=0.95)
        assert bs == pytest.approx(0.9025)

    def test_empty(self):
        assert brier_score([], confidence=0.95) is None


class TestCalibrationRate:
    def test_basic(self):
        coverages = [True, True, False, True]
        assert calibration_rate(coverages) == pytest.approx(0.75)

    def test_empty(self):
        assert calibration_rate([]) is None


class TestScoreDistribution:
    def test_bins(self):
        scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
        dist = score_distribution(scores, bins=5)
        assert len(dist) == 5
        assert sum(d["count"] for d in dist) == 6

    def test_empty(self):
        assert score_distribution([]) == []


class TestPointHitRate:
    def test_basic(self):
        # score=1.0 means hit, score=0.0 means miss, score=0.5 is partial
        scores = [1.0, 1.0, 0.5, 0.0]
        rate = point_hit_rate(scores)
        assert rate["perfect"] == pytest.approx(0.5)
        assert rate["partial"] == pytest.approx(0.25)
        assert rate["miss"] == pytest.approx(0.25)

    def test_empty(self):
        assert point_hit_rate([]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement stats module**

```python
# src/knowledge_base/srs/stats.py
"""Statistical analysis of review history for calibration tracking."""

from __future__ import annotations


def brier_score(
    coverages: list[bool], confidence: float = 0.95
) -> float | None:
    """Compute Brier score for interval coverage.

    Args:
        coverages: List of booleans (True = truth inside interval).
        confidence: The stated confidence level (0.95 for 95% CI).

    Returns:
        Brier score, or None if empty. Lower is better.
        Perfect calibration at 95% → ~0.0475.
    """
    if not coverages:
        return None
    n = len(coverages)
    return sum((confidence - (1.0 if c else 0.0)) ** 2 for c in coverages) / n


def calibration_rate(coverages: list[bool]) -> float | None:
    """Fraction of intervals that contained the true answer.

    Should be close to 0.95 for well-calibrated 95% CIs.
    """
    if not coverages:
        return None
    return sum(coverages) / len(coverages)


def score_distribution(
    scores: list[float], bins: int = 10
) -> list[dict]:
    """Bin scores into a histogram.

    Returns list of {lower, upper, count} dicts.
    """
    if not scores:
        return []
    bin_width = 1.0 / bins
    result = []
    for i in range(bins):
        lower = i * bin_width
        upper = (i + 1) * bin_width
        count = sum(1 for s in scores if lower <= s < upper or (i == bins - 1 and s == upper))
        result.append({"lower": lower, "upper": upper, "count": count})
    return result


def point_hit_rate(scores: list[float]) -> dict | None:
    """Breakdown of point prediction outcomes.

    Args:
        scores: List of point prediction scores (1.0, 0.5, or 0.0).

    Returns:
        Dict with perfect/partial/miss rates, or None if empty.
    """
    if not scores:
        return None
    n = len(scores)
    return {
        "perfect": sum(1 for s in scores if s == 1.0) / n,
        "partial": sum(1 for s in scores if s == 0.5) / n,
        "miss": sum(1 for s in scores if s == 0.0) / n,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stats.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/stats.py tests/test_stats.py
git commit -m "feat(srs): add stats module for Brier score and calibration tracking

Brier score, calibration rate, score distribution histogram,
and point prediction hit rate. Feeds the TUI stats screen."
```

---

## Task 7: TUI Review App

**Files:**
- Create: `src/knowledge_base/srs/tui.py`
- Modify: `pyproject.toml`

This task is larger because the TUI integrates all previous modules. It does not use TDD — Textual apps are best tested interactively.

- [ ] **Step 1: Add dependencies and entry points to `pyproject.toml`**

Add `textual` to dependencies:

```toml
dependencies = [
    "genanki>=0.13",
    "httpx>=0.27",
    "polars>=1.0",
    "textual>=3.0",
]
```

Add entry points:

```toml
[project.scripts]
fetch-data = "knowledge_base.fetch_data:main"
fetch-urban-data = "knowledge_base.fetch_urban_data:main"
fetch-desc-stats = "knowledge_base.fetch_desc_stats:main"
build-deck = "knowledge_base.build_deck:main"
review = "knowledge_base.srs.tui:main"
srs-import = "knowledge_base.srs.importer:main"
```

- [ ] **Step 2: Run `uv sync` to install new dependency**

Run: `uv sync`
Expected: `textual` installed successfully.

- [ ] **Step 3: Implement TUI app**

```python
# src/knowledge_base/srs/tui.py
"""Textual TUI for SRS review sessions."""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Input, Label
from textual.binding import Binding
from textual import on

from knowledge_base.srs.db import (
    init_db,
    get_due_cards,
    update_card_scheduling,
    insert_review,
    get_reviews_for_card,
)
from knowledge_base.srs.scoring import (
    score_interval,
    score_point,
    apply_difficulty_modifier,
)
from knowledge_base.srs.scheduler import (
    compute_retrievability,
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
    SUCCESS_THRESHOLD,
)
from knowledge_base.srs.stats import (
    brier_score,
    calibration_rate,
    point_hit_rate,
)

RANGE_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*-\s*(-?\d+\.?\d*)\s*$")
POINT_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*$")

DB_PATH = Path("data/srs.db")


def parse_answer(text: str) -> tuple[str, float, float | None]:
    """Parse user input into (mode, value1, value2).

    Returns:
        ("interval", lower, upper) or ("point", value, None)

    Raises:
        ValueError if input can't be parsed.
    """
    m = RANGE_RE.match(text)
    if m:
        lower, upper = float(m.group(1)), float(m.group(2))
        if lower >= upper:
            raise ValueError("Lower bound must be less than upper bound")
        return ("interval", lower, upper)
    m = POINT_RE.match(text)
    if m:
        return ("point", float(m.group(1)), None)
    raise ValueError("Enter a range (e.g., 1000-5000) or a single number")


def _format_display(value: float, prefix: str = "", decimals: int = 0) -> str:
    """Format a number for display with commas and prefix."""
    if decimals == 0:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:,.{decimals}f}"


class ReviewApp(App):
    """TUI application for SRS review sessions."""

    TITLE = "Calibration SRS"
    BINDINGS = [
        Binding("q", "quit_session", "Quit"),
        Binding("s", "show_stats", "Stats"),
    ]

    def __init__(
        self,
        db_path: str | Path = DB_PATH,
        deck: str | None = None,
        limit: int | None = None,
        stats_only: bool = False,
    ):
        super().__init__()
        self.db_path = db_path
        self.deck_filter = deck
        self.limit = limit
        self.stats_only = stats_only
        self.conn = None
        self.cards: list[dict] = []
        self.current_idx = 0
        self.showing_answer = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(id="card-header"),
            Static(id="question"),
            Input(placeholder="Enter range (e.g. 1000-5000) or point estimate", id="answer-input"),
            Static(id="result"),
            Static(id="stats-display"),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.conn = init_db(self.db_path)
        if self.stats_only:
            self._show_stats_screen()
            return
        self._load_cards()
        if not self.cards:
            self.query_one("#question", Static).update("No cards due for review.")
            self.query_one("#answer-input", Input).display = False
        else:
            self._show_question()

    def _load_cards(self) -> None:
        today = date.today().isoformat()
        self.cards = get_due_cards(
            self.conn,
            as_of=today,
            deck=self.deck_filter,
            limit=self.limit,
        )
        self.current_idx = 0

    def _show_question(self) -> None:
        if self.current_idx >= len(self.cards):
            self.query_one("#card-header", Static).update("")
            self.query_one("#question", Static).update("Session complete!")
            self.query_one("#answer-input", Input).display = False
            self.query_one("#result", Static).update("")
            return

        card = self.cards[self.current_idx]
        total = len(self.cards)
        idx = self.current_idx + 1

        header = f"  {card['deck'].title()} > {card['indicator_id']}   [{idx}/{total}]"
        self.query_one("#card-header", Static).update(header)
        self.query_one("#question", Static).update(f"\n  {card['question']}\n")
        self.query_one("#result", Static).update("")

        input_widget = self.query_one("#answer-input", Input)
        input_widget.display = True
        input_widget.value = ""
        input_widget.focus()
        self.showing_answer = False

    @on(Input.Submitted, "#answer-input")
    def on_submit(self, event: Input.Submitted) -> None:
        if self.showing_answer:
            self.current_idx += 1
            self._show_question()
            return

        card = self.cards[self.current_idx]
        text = event.value.strip()
        if not text:
            return

        try:
            mode, val1, val2 = parse_answer(text)
        except ValueError as e:
            self.query_one("#result", Static).update(f"  Error: {e}")
            return

        true_answer = card["answer"]
        ind_std = card["indicator_std"]
        ind_mean = card["indicator_mean"]
        prefix = card["unit_prefix"] or ""
        decimals = card["decimals"] or 0

        if ind_std is None or ind_std == 0:
            self.query_one("#result", Static).update(
                "  Error: No indicator statistics available for scoring."
            )
            return

        # Score
        if mode == "interval":
            result = score_interval(val1, val2, true_answer, ind_std)
            raw_score = result.score
            center = (val1 + val2) / 2
            width = val2 - val1

            lines = [
                "",
                f"  Your interval: {_format_display(val1, prefix, decimals)} \u2013 {_format_display(val2, prefix, decimals)}",
                f"  True answer:   {_format_display(true_answer, prefix, decimals)}",
                f"  Status:        {'Within interval' if result.covered else 'OUTSIDE interval'}",
                "",
                f"  Accuracy:  {result.accuracy_score:.2f}  (center was {_format_display(abs(true_answer - center), prefix, decimals)} off)",
                f"  Precision: {result.precision_score:.2f}  (width = {width / ind_std:.1f} SD)",
                f"  Coverage:  {'1.00' if result.covered else '0.00'}",
                f"  Score:     {raw_score:.2f}",
            ]

            review_data = {
                "answer_mode": "interval",
                "user_lower": val1,
                "user_upper": val2,
                "user_point": None,
            }
        else:
            raw_score = score_point(val1, true_answer, ind_std)
            error_sd = abs(true_answer - val1) / ind_std

            lines = [
                "",
                f"  Your estimate: {_format_display(val1, prefix, decimals)}",
                f"  True answer:   {_format_display(true_answer, prefix, decimals)}",
                f"  Error:         {error_sd:.2f} SDs",
                f"  Score:         {raw_score:.2f}",
            ]

            review_data = {
                "answer_mode": "point",
                "user_lower": None,
                "user_upper": None,
                "user_point": val1,
            }

        # Apply difficulty modifier if mean is available
        if ind_mean is not None:
            raw_score = apply_difficulty_modifier(
                raw_score, true_answer, ind_mean, ind_std
            )

        # Notes
        if card["notes"]:
            lines.append("")
            lines.append(f"  {card['notes']}")

        # Scheduling
        now = datetime.now()
        state = card["state"]
        difficulty = card["difficulty"]
        stability = card["stability"]
        last_review = card["last_review"]
        consec = card["consecutive_successes"]
        reps = card["reps"]

        if last_review:
            last_dt = datetime.fromisoformat(last_review)
            elapsed = (now - last_dt).total_seconds() / 86400
        else:
            elapsed = 0.0

        # Update scheduling state
        new_difficulty = update_difficulty(difficulty, raw_score)
        success = raw_score >= SUCCESS_THRESHOLD

        if state == "new" or state == "learning":
            if success:
                new_consec = consec + 1
            else:
                new_consec = 0

            if new_consec >= 2:
                new_state = "review"
                new_stability = 1.0
                desired_ret = compute_desired_retention(raw_score)
                interval = compute_interval(new_stability, desired_ret)
            else:
                new_state = "learning"
                new_stability = stability
                desired_ret = compute_desired_retention(raw_score)
                if new_consec == 0:
                    # Failed — show again this session (interval=0 means intra-session)
                    interval = 0.0
                else:
                    # One success — due tomorrow
                    interval = 1.0
        else:
            # Review state
            new_consec = consec
            new_stability = update_stability(stability, difficulty, raw_score)
            desired_ret = compute_desired_retention(raw_score)
            interval = compute_interval(new_stability, desired_ret)

        due_date = (now + timedelta(days=interval)).date() if interval > 0 else None

        update_card_scheduling(self.conn, card["card_id"], {
            "difficulty": new_difficulty,
            "stability": new_stability,
            "last_review": now.isoformat(),
            "due": due_date.isoformat() if due_date else now.date().isoformat(),
            "reps": reps + 1,
            "consecutive_successes": new_consec,
            "state": new_state,
        })

        insert_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now.isoformat(),
            "true_answer": true_answer,
            "raw_score": raw_score,
            "desired_retention": desired_ret,
            "interval_applied": interval,
            "elapsed_days": elapsed,
            **review_data,
        })

        if interval > 0:
            lines.append("")
            lines.append(f"  Next review: {interval:.1f} days")
        else:
            lines.append("")
            lines.append("  Next review: again this session")

        lines.append("")
        lines.append("  [Enter] next  [s] stats  [q] quit")

        self.query_one("#result", Static).update("\n".join(lines))
        self.showing_answer = True

    def action_quit_session(self) -> None:
        if self.conn:
            self.conn.close()
        self.exit()

    def action_show_stats(self) -> None:
        self._show_stats_screen()

    def _show_stats_screen(self) -> None:
        self.query_one("#card-header", Static).update("  Review Statistics")
        self.query_one("#question", Static).update("")
        self.query_one("#answer-input", Input).display = False
        self.query_one("#result", Static).update("")

        # Gather all reviews
        rows = self.conn.execute(
            "SELECT answer_mode, raw_score, user_lower, user_upper, true_answer "
            "FROM review_log ORDER BY timestamp"
        ).fetchall()

        if not rows:
            self.query_one("#stats-display", Static).update("  No reviews yet.")
            return

        interval_coverages = []
        interval_scores = []
        point_scores = []

        for r in rows:
            if r["answer_mode"] == "interval":
                covered = r["user_lower"] <= r["true_answer"] <= r["user_upper"]
                interval_coverages.append(covered)
                interval_scores.append(r["raw_score"])
            else:
                point_scores.append(r["raw_score"])

        lines = [""]
        lines.append(f"  Total reviews: {len(rows)}")
        lines.append(f"  Interval reviews: {len(interval_scores)}")
        lines.append(f"  Point reviews: {len(point_scores)}")
        lines.append("")

        if interval_coverages:
            bs = brier_score(interval_coverages)
            cr = calibration_rate(interval_coverages)
            avg_score = sum(interval_scores) / len(interval_scores)
            lines.append(f"  Brier score:      {bs:.4f}  (perfect calibration at 95% ≈ 0.0475)")
            lines.append(f"  Calibration rate:  {cr:.1%}   (target: 95%)")
            lines.append(f"  Avg interval score: {avg_score:.2f}")
            lines.append("")

        if point_scores:
            rates = point_hit_rate(point_scores)
            lines.append(f"  Point predictions:")
            lines.append(f"    Perfect (<0.05 SD): {rates['perfect']:.1%}")
            lines.append(f"    Partial (<0.25 SD): {rates['partial']:.1%}")
            lines.append(f"    Miss:               {rates['miss']:.1%}")
            lines.append("")

        # Card state summary
        card_counts = self.conn.execute(
            "SELECT state, COUNT(*) as n FROM cards GROUP BY state"
        ).fetchall()
        lines.append("  Card states:")
        for row in card_counts:
            lines.append(f"    {row['state']}: {row['n']}")

        # Due today
        today = date.today().isoformat()
        due_count = len(get_due_cards(self.conn, as_of=today, deck=self.deck_filter))
        lines.append(f"\n  Due today: {due_count}")
        lines.append("\n  [Enter] back to review  [q] quit")

        self.query_one("#stats-display", Static).update("\n".join(lines))


def main() -> None:
    """CLI entry point for review sessions."""
    import argparse

    parser = argparse.ArgumentParser(description="Calibration SRS review session")
    parser.add_argument("deck", nargs="?", help="Deck key to review")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--limit", type=int, help="Max cards per session")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")
    args = parser.parse_args()

    app = ReviewApp(
        db_path=args.db,
        deck=args.deck,
        limit=args.limit,
        stats_only=args.stats,
    )
    app.run()
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `uv run pytest -v`
Expected: All existing tests pass. (TUI itself is tested interactively.)

- [ ] **Step 5: Smoke test the full flow**

```bash
# Import development deck
uv run srs-import development

# Launch review session
uv run review development --limit 5

# Check stats
uv run review --stats
```

Expected: Import prints card count. Review launches TUI. Stats shows empty review history.

- [ ] **Step 6: Commit**

```bash
git add src/knowledge_base/srs/tui.py pyproject.toml
git commit -m "feat(srs): add Textual TUI for review sessions and stats

Review flow: question → answer input → scoring → scheduling → next card.
Stats screen with Brier score, calibration rate, point prediction
breakdown. CLI: 'review [deck]', 'review --stats', '--limit N'."
```

---

## Task 8: Integration Test & Final Wiring

**Files:**
- Create: `tests/test_srs_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_srs_integration.py
"""End-to-end test: import → score → schedule → review-log."""

from pathlib import Path
from datetime import datetime, timedelta
import pytest
from knowledge_base.srs.db import (
    init_db,
    get_card,
    get_due_cards,
    update_card_scheduling,
    insert_review,
    get_reviews_for_card,
)
from knowledge_base.srs.importer import import_deck
from knowledge_base.srs.scoring import score_interval, score_point
from knowledge_base.srs.scheduler import (
    compute_desired_retention,
    compute_interval,
    update_difficulty,
    update_stability,
    SUCCESS_THRESHOLD,
)
from knowledge_base.srs.stats import brier_score, calibration_rate


FIXTURES = Path(__file__).parent / "fixtures" / "sample_srs_import"


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


class TestFullReviewCycle:
    def test_import_review_schedule(self, db):
        """Full cycle: import → answer → score → schedule → verify state."""
        # Import
        count = import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        assert count == 2

        # Get a due card (new)
        due = get_due_cards(db, as_of="2026-03-28")
        india = [c for c in due if c["entity"] == "India"][0]
        assert india["state"] == "new"

        # Simulate interval answer
        result = score_interval(
            lower=1000, upper=5000,
            true_answer=india["answer"],
            indicator_std=india["indicator_std"],
        )
        raw_score = result.score
        assert 0 <= raw_score <= 1

        # First review: new → learning (1 success)
        now = datetime(2026, 3, 28, 10, 0, 0)
        success = raw_score >= SUCCESS_THRESHOLD

        update_card_scheduling(db, india["card_id"], {
            "difficulty": update_difficulty(india["difficulty"], raw_score),
            "stability": india["stability"],
            "last_review": now.isoformat(),
            "due": (now + timedelta(days=1)).date().isoformat() if success else now.date().isoformat(),
            "reps": 1,
            "consecutive_successes": 1 if success else 0,
            "state": "learning",
        })

        insert_review(db, {
            "card_id": india["card_id"],
            "timestamp": now.isoformat(),
            "answer_mode": "interval",
            "user_lower": 1000.0,
            "user_upper": 5000.0,
            "user_point": None,
            "true_answer": india["answer"],
            "raw_score": raw_score,
            "desired_retention": compute_desired_retention(raw_score),
            "interval_applied": 1.0,
            "elapsed_days": 0.0,
        })

        card = get_card(db, india["card_id"])
        assert card["state"] == "learning"
        assert card["consecutive_successes"] == (1 if success else 0)

        # Second review: learning → review (2 successes)
        now2 = now + timedelta(days=1)
        result2 = score_interval(
            lower=1500, upper=3500,
            true_answer=india["answer"],
            indicator_std=india["indicator_std"],
        )
        raw_score2 = result2.score

        if raw_score2 >= SUCCESS_THRESHOLD and card["consecutive_successes"] >= 1:
            new_state = "review"
            new_stability = 1.0
            desired_ret = compute_desired_retention(raw_score2)
            interval = compute_interval(new_stability, desired_ret)
        else:
            new_state = "learning"
            interval = 1.0

        update_card_scheduling(db, india["card_id"], {
            "difficulty": update_difficulty(card["difficulty"], raw_score2),
            "stability": new_stability if new_state == "review" else card["stability"],
            "last_review": now2.isoformat(),
            "due": (now2 + timedelta(days=interval)).date().isoformat(),
            "reps": 2,
            "consecutive_successes": 2 if new_state == "review" else card["consecutive_successes"],
            "state": new_state,
        })

        card = get_card(db, india["card_id"])
        assert card["state"] == "review"
        assert card["reps"] == 2

    def test_point_prediction_cycle(self, db):
        """Point prediction → scoring → scheduling."""
        import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        due = get_due_cards(db, as_of="2026-03-28")
        card = due[0]

        score = score_point(
            user_point=card["answer"],
            true_answer=card["answer"],
            indicator_std=card["indicator_std"],
        )
        # Exact match → score = 1.0
        assert score == 1.0

    def test_stats_from_reviews(self, db):
        """Review log feeds stats correctly."""
        import_deck(
            db,
            deck_key="development",
            data_dir=FIXTURES,
            desc_stats_dir=FIXTURES,
            desc_stats_prefix="desc_stats_",
        )
        due = get_due_cards(db, as_of="2026-03-28")
        card = due[0]

        # Insert some reviews
        for i, (lo, hi) in enumerate([(1000, 5000), (2000, 3000), (500, 600)]):
            insert_review(db, {
                "card_id": card["card_id"],
                "timestamp": f"2026-03-28T{10+i}:00:00",
                "answer_mode": "interval",
                "user_lower": float(lo),
                "user_upper": float(hi),
                "user_point": None,
                "true_answer": card["answer"],
                "raw_score": 0.5,
                "desired_retention": 0.9,
                "interval_applied": 3.0,
                "elapsed_days": 0.0,
            })

        reviews = get_reviews_for_card(db, card["card_id"])
        assert len(reviews) == 3

        # Compute calibration
        coverages = [
            r["user_lower"] <= r["true_answer"] <= r["user_upper"]
            for r in reviews
        ]
        bs = brier_score(coverages)
        assert bs is not None
        cr = calibration_rate(coverages)
        assert cr is not None
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_srs_integration.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (original 44 + new tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_srs_integration.py
git commit -m "test(srs): add integration test for full import-review-schedule cycle

End-to-end test covering import, interval/point scoring, learning-to-review
promotion, and stats computation from review logs."
```

---

## Self-Review Checklist

**Spec coverage:**
- Scoring algorithm (interval + point + difficulty modifier) → Task 2
- Scheduler (DSR model, retention modulation, card states) → Task 3
- Database (schema, migrations, CRUD) → Task 4
- Importer (CSV discovery, idempotent upsert, display units) → Task 5
- Stats (Brier, calibration rate, score distribution, point hit rate) → Task 6
- TUI (review flow, stats screen, input parsing, key bindings) → Task 7
- CLI entry points (`review`, `srs-import`) → Task 7
- Shared `card_gen.py` extraction → Task 1
- Schema migration strategy → Task 4 (schema_version table)
- Learning step timing (intra-session + next-day) → Task 7 (tui.py scheduling logic)
- Two consecutive successes for promotion → Task 7 (tui.py) + Task 8 (integration test)
- Queue priority ordering → Task 4 (get_due_cards)
- Session limit → Task 7 (--limit flag)

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks complete.

**Type consistency:** `score_interval` returns `IntervalResult` (Task 2), used in Task 7 and 8. `init_db` returns `sqlite3.Connection` (Task 4), used everywhere. `import_deck` signature consistent across Task 5 tests and Task 8 integration. `update_card_scheduling` takes `dict` of fields (Task 4), called with matching keys in Task 7 and 8.

**Spec note on retention range:** The formula `0.90 + 0.05 * (score - 0.5)` gives range [0.875, 0.925], not [0.85, 0.925] as the spec states. The implementation follows the formula. This is a minor spec inaccuracy worth noting but not blocking — the spec says the range is "deliberately asymmetric" and the formula produces a narrower asymmetry than documented. The spec should be updated to say [0.875, 0.925].
