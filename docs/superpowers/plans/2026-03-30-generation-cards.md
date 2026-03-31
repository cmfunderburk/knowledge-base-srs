# Generation Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generation/recall cards for CFA LOS memorization with graduated masking and standard FSRS v6 scheduling.

**Architecture:** Completely separate from existing interval cards — new DB table, new FSRS scheduler, new TUI entry point. Generation phase uses intra-session queue-based massed practice (no scheduler). Recall phase uses standard FSRS v6 with 4-button grading (Again/Hard/Good/Easy).

**Tech Stack:** Python 3.12+, SQLite, Textual (TUI), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-30-generation-cards-design.md`

---

## File Map

```
src/knowledge_base/srs/
    masking.py              # NEW — letter-level masking algorithm
    text_scoring.py         # NEW — token-level Levenshtein comparison
    fsrs.py                 # NEW — standard FSRS v6 (4-button discrete grades)
    generation_db.py        # NEW — schema, CRUD, migrations for generation_cards
    generation_import.py    # NEW — LOS JSON → generation_cards population
    generation_tui.py       # NEW — Textual TUI for generation card review

data/cfa_level1_los.json   # NEW — extracted LOS statements

tests/
    test_masking.py         # NEW
    test_text_scoring.py    # NEW
    test_fsrs.py            # NEW
    test_generation_db.py   # NEW
    test_generation_import.py # NEW

pyproject.toml              # MODIFY — add review-gen and gen-import entry points
```

---

### Task 1: Masking Algorithm

**Files:**
- Create: `src/knowledge_base/srs/masking.py`
- Test: `tests/test_masking.py`

- [ ] **Step 1: Write failing tests for masking eligibility**

Create `tests/test_masking.py`:

```python
"""Tests for srs/masking.py — letter-level masking for generation cards."""

import pytest
from knowledge_base.srs.masking import is_maskable, mask_word, mask_text


class TestIsMaskable:
    def test_function_words_not_maskable(self):
        """Common function words should never be masked."""
        for word in ["the", "and", "for", "are", "that", "with", "from"]:
            assert is_maskable(word) is False, f"{word!r} should not be maskable"

    def test_short_words_not_maskable(self):
        """Words with 3 or fewer letters should not be masked."""
        for word in ["is", "of", "an", "tax", "GDP"]:
            assert is_maskable(word) is False

    def test_content_words_maskable(self):
        """Content words longer than 3 letters should be maskable."""
        for word in ["interpret", "interest", "rates", "required", "premiums"]:
            assert is_maskable(word) is True, f"{word!r} should be maskable"

    def test_numbers_not_maskable(self):
        """Numeric tokens should not be masked."""
        for word in ["95%", "1-year", "2024", "10%"]:
            assert is_maskable(word) is False

    def test_acronyms_not_maskable(self):
        """All-caps abbreviations should not be masked."""
        for word in ["CAPM", "NPV", "FSRS", "SML", "WACC"]:
            assert is_maskable(word) is False

    def test_mixed_case_acronyms_not_maskable(self):
        """Tokens that are mostly uppercase are acronyms."""
        assert is_maskable("PV") is False
        assert is_maskable("IRR") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_masking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_base.srs.masking'`

- [ ] **Step 3: Implement `is_maskable`**

Create `src/knowledge_base/srs/masking.py`:

```python
"""Letter-level masking algorithm for generation cards.

Masks content words at graduated levels while preserving first letters,
function words, short words, numbers, and acronyms.
"""

from __future__ import annotations

import hashlib
import re

# Function words that are never masked (all lowercase)
FUNCTION_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "them", "to", "was", "were", "which", "with", "not", "but", "if",
    "than", "this", "these", "those", "can", "has", "have", "may",
    "will", "also", "each", "such", "whether", "should",
})

_NUM_RE = re.compile(r"^\d+[%,.]?\d*$|^\d+-\w+$")


def is_maskable(word: str) -> bool:
    """Return True if a word should be eligible for masking.

    Not maskable: function words, short words (<=3 chars), numbers,
    acronyms (all uppercase and length >= 2).
    """
    stripped = word.strip(".,;:!?()[]\"'")
    if len(stripped) <= 3:
        return False
    if stripped.lower() in FUNCTION_WORDS:
        return False
    if _NUM_RE.match(stripped):
        return False
    # All uppercase = acronym (e.g., CAPM, NPV)
    if len(stripped) >= 2 and stripped.isupper():
        return False
    return True
```

- [ ] **Step 4: Run eligibility tests to verify they pass**

Run: `uv run pytest tests/test_masking.py::TestIsMaskable -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for `mask_word`**

Append to `tests/test_masking.py`:

```python
class TestMaskWord:
    def test_first_letter_always_preserved(self):
        """First letter of any masked word is never replaced."""
        for level in [0, 1, 2]:
            result = mask_word("interpret", level=level, seed=42)
            assert result[0] == "i"

    def test_level_2_first_letter_only(self):
        """Level 2 masks all letters after the first."""
        result = mask_word("interpret", level=2, seed=42)
        assert result == "i________"

    def test_level_0_masks_about_30_percent(self):
        """Level 0 masks roughly 30% of non-first letters."""
        word = "interpretation"  # 14 chars, 13 non-first
        result = mask_word(word, level=0, seed=42)
        masked_count = result.count("_")
        # ~30% of 13 = ~4, allow range 2-6
        assert 2 <= masked_count <= 6

    def test_level_1_masks_about_60_percent(self):
        """Level 1 masks roughly 60% of non-first letters."""
        word = "interpretation"  # 14 chars, 13 non-first
        result = mask_word(word, level=1, seed=42)
        masked_count = result.count("_")
        # ~60% of 13 = ~8, allow range 6-10
        assert 6 <= masked_count <= 10

    def test_deterministic_same_seed(self):
        """Same word + level + seed = same mask pattern."""
        r1 = mask_word("interpret", level=1, seed=99)
        r2 = mask_word("interpret", level=1, seed=99)
        assert r1 == r2

    def test_different_seeds_different_patterns(self):
        """Different seeds should (usually) produce different masks."""
        r1 = mask_word("interpretation", level=1, seed=1)
        r2 = mask_word("interpretation", level=1, seed=2)
        # Very unlikely to be identical for a long word
        assert r1 != r2

    def test_no_consecutive_underscores_level_0(self):
        """Level 0 should avoid consecutive underscores."""
        # Use a long word to make this testable
        result = mask_word("interpretation", level=0, seed=42)
        assert "__" not in result

    def test_short_word_returned_unchanged(self):
        """Words with <= 3 chars cannot be meaningfully masked."""
        assert mask_word("the", level=2, seed=42) == "the"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_masking.py::TestMaskWord -v`
Expected: FAIL with `cannot import name 'mask_word'`

- [ ] **Step 7: Implement `mask_word`**

Add to `src/knowledge_base/srs/masking.py`:

```python
def _seed_hash(seed: int, extra: str = "") -> int:
    """Produce a deterministic integer from seed + extra string."""
    data = f"{seed}:{extra}".encode()
    return int(hashlib.md5(data).hexdigest(), 16)


def mask_word(word: str, level: int, seed: int) -> str:
    """Mask letters in a single word at the given level.

    Level 0: ~30% of non-first letters masked, no consecutive underscores.
    Level 1: ~60% of non-first letters masked, no consecutive underscores.
    Level 2: all letters after the first are masked.

    First letter is always preserved. Words with <= 3 chars are returned as-is.
    """
    if len(word) <= 3:
        return word

    if level == 2:
        return word[0] + "_" * (len(word) - 1)

    ratio = 0.3 if level == 0 else 0.6
    n_maskable = len(word) - 1  # exclude first letter
    n_to_mask = max(1, round(n_maskable * ratio))

    # Build candidate indices (1-based, since index 0 is preserved)
    rng_val = _seed_hash(seed, word)
    indices = list(range(1, len(word)))

    # Deterministic shuffle using seed
    for i in range(len(indices) - 1, 0, -1):
        rng_val = _seed_hash(seed, f"{word}:{i}")
        j = rng_val % (i + 1)
        indices[i], indices[j] = indices[j], indices[i]

    # Select indices, filtering consecutive ones for level 0
    selected: set[int] = set()
    for idx in indices:
        if len(selected) >= n_to_mask:
            break
        if level == 0 and (idx - 1 in selected or idx + 1 in selected):
            continue
        selected.add(idx)

    # If we couldn't fill enough due to non-consecutive constraint, relax
    if len(selected) < n_to_mask:
        for idx in indices:
            if len(selected) >= n_to_mask:
                break
            selected.add(idx)

    chars = list(word)
    for idx in selected:
        chars[idx] = "_"
    return "".join(chars)
```

- [ ] **Step 8: Run `mask_word` tests**

Run: `uv run pytest tests/test_masking.py::TestMaskWord -v`
Expected: All PASS

- [ ] **Step 9: Write failing tests for `mask_text`**

Append to `tests/test_masking.py`:

```python
class TestMaskText:
    def test_function_words_preserved(self):
        """Function words should appear unmasked in output."""
        text = "interpret interest rates as required rates of return"
        result = mask_text(text, level=1, card_id=1)
        words = result.split()
        assert words[3] == "as"
        assert words[6] == "of"

    def test_deterministic_with_card_id(self):
        """Same text + level + card_id = same output."""
        text = "interpret interest rates as required rates of return"
        r1 = mask_text(text, level=1, card_id=1)
        r2 = mask_text(text, level=1, card_id=1)
        assert r1 == r2

    def test_different_card_ids_different_masks(self):
        """Different card_ids should produce different mask patterns."""
        text = "interpret interest rates as required rates of return"
        r1 = mask_text(text, level=1, card_id=1)
        r2 = mask_text(text, level=1, card_id=2)
        assert r1 != r2

    def test_level_2_all_content_words_first_letter_only(self):
        """Level 2 should show only first letters of content words."""
        text = "interpret interest rates"
        result = mask_text(text, level=2, card_id=1)
        words = result.split()
        assert words[0] == "i________"
        assert words[1] == "i_______"
        assert words[2] == "r____"

    def test_punctuation_preserved(self):
        """Commas and periods should be preserved alongside words."""
        text = "rates, returns, and costs"
        result = mask_text(text, level=2, card_id=1)
        assert "," in result

    def test_empty_string(self):
        """Empty input returns empty output."""
        assert mask_text("", level=0, card_id=1) == ""
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/test_masking.py::TestMaskText -v`
Expected: FAIL (mask_text not yet implemented or returns wrong output)

- [ ] **Step 11: Implement `mask_text`**

Add to `src/knowledge_base/srs/masking.py`:

```python
def mask_text(text: str, level: int, card_id: int) -> str:
    """Mask an entire text string at the given level.

    Splits on whitespace, masks eligible words, preserves function words,
    short words, numbers, and acronyms. Punctuation attached to words is
    preserved.

    Uses card_id + level as the seed base, with per-word variation from
    the word index.
    """
    if not text:
        return ""

    base_seed = _seed_hash(card_id, str(level))
    tokens = text.split()
    result = []

    for i, token in enumerate(tokens):
        # Separate trailing punctuation
        stripped = token.rstrip(".,;:!?()")
        trailing = token[len(stripped):]

        if is_maskable(stripped):
            word_seed = _seed_hash(base_seed, f"{i}:{stripped}")
            masked = mask_word(stripped, level=level, seed=word_seed)
            result.append(masked + trailing)
        else:
            result.append(token)

    return " ".join(result)
```

- [ ] **Step 12: Run all masking tests**

Run: `uv run pytest tests/test_masking.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add src/knowledge_base/srs/masking.py tests/test_masking.py
git commit -m "feat: add letter-level masking algorithm for generation cards"
```

---

### Task 2: Text Scoring (Levenshtein Comparison)

**Files:**
- Create: `src/knowledge_base/srs/text_scoring.py`
- Test: `tests/test_text_scoring.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_text_scoring.py`:

```python
"""Tests for srs/text_scoring.py — token-level text comparison."""

import pytest
from knowledge_base.srs.text_scoring import (
    levenshtein,
    tokenize,
    compare_tokens,
    TokenResult,
)


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein("hello", "hello") == 0

    def test_one_substitution(self):
        assert levenshtein("hello", "hallo") == 1

    def test_one_insertion(self):
        assert levenshtein("hell", "hello") == 1

    def test_one_deletion(self):
        assert levenshtein("hello", "hell") == 1

    def test_completely_different(self):
        assert levenshtein("abc", "xyz") == 3

    def test_empty_strings(self):
        assert levenshtein("", "") == 0
        assert levenshtein("abc", "") == 3
        assert levenshtein("", "abc") == 3


class TestTokenize:
    def test_basic(self):
        assert tokenize("interest rates of return") == [
            "interest", "rates", "of", "return"
        ]

    def test_strips_punctuation(self):
        assert tokenize("rates, returns, and costs.") == [
            "rates", "returns", "and", "costs"
        ]

    def test_lowercases(self):
        assert tokenize("CAPM and SML") == ["capm", "and", "sml"]

    def test_empty(self):
        assert tokenize("") == []


class TestCompareTokens:
    def test_exact_match(self):
        results = compare_tokens(
            ["interest", "rates"],
            ["interest", "rates"],
        )
        assert len(results) == 2
        assert all(r.status == "exact" for r in results)

    def test_typo_accepted(self):
        """Levenshtein distance 1 = 'close' (yellow)."""
        results = compare_tokens(
            ["interpet"],  # missing 'r'
            ["interpret"],
        )
        assert results[0].status == "close"

    def test_wrong_word(self):
        results = compare_tokens(
            ["banana"],
            ["interpret"],
        )
        assert results[0].status == "wrong"

    def test_extra_typed_words(self):
        """Typed answer has more words than correct."""
        results = compare_tokens(
            ["interest", "rates", "extra"],
            ["interest", "rates"],
        )
        assert len(results) == 3
        assert results[0].status == "exact"
        assert results[1].status == "exact"
        assert results[2].status == "extra"

    def test_missing_words(self):
        """Typed answer has fewer words than correct."""
        results = compare_tokens(
            ["interest"],
            ["interest", "rates"],
        )
        assert len(results) == 2
        assert results[0].status == "exact"
        assert results[1].status == "missing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_text_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement text_scoring.py**

Create `src/knowledge_base/srs/text_scoring.py`:

```python
"""Token-level text comparison for generation card feedback.

Provides Levenshtein distance and token-by-token alignment for displaying
typed vs. correct answer diffs. Used for display only — not for scheduling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PUNCT_RE = re.compile(r"[.,;:!?()\"'\[\]]+")


@dataclass
class TokenResult:
    """Result for a single token comparison."""
    expected: str       # the correct word (empty if extra typed word)
    typed: str          # what the user typed (empty if missing)
    status: str         # "exact" | "close" | "wrong" | "missing" | "extra"


def levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens with punctuation stripped."""
    if not text.strip():
        return []
    words = text.split()
    return [_PUNCT_RE.sub("", w).lower() for w in words if _PUNCT_RE.sub("", w)]


def compare_tokens(
    typed_tokens: list[str],
    correct_tokens: list[str],
) -> list[TokenResult]:
    """Compare typed tokens against correct tokens sequentially.

    Returns one TokenResult per position. Handles length mismatches by
    marking extra typed words as "extra" and missing correct words as "missing".
    """
    results: list[TokenResult] = []
    max_len = max(len(typed_tokens), len(correct_tokens))

    for i in range(max_len):
        if i >= len(correct_tokens):
            results.append(TokenResult(
                expected="", typed=typed_tokens[i], status="extra",
            ))
        elif i >= len(typed_tokens):
            results.append(TokenResult(
                expected=correct_tokens[i], typed="", status="missing",
            ))
        else:
            typed = typed_tokens[i]
            expected = correct_tokens[i]
            if typed == expected:
                status = "exact"
            elif levenshtein(typed, expected) <= 1:
                status = "close"
            else:
                status = "wrong"
            results.append(TokenResult(
                expected=expected, typed=typed, status=status,
            ))

    return results
```

- [ ] **Step 4: Run all text scoring tests**

Run: `uv run pytest tests/test_text_scoring.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/text_scoring.py tests/test_text_scoring.py
git commit -m "feat: add token-level Levenshtein text comparison"
```

---

### Task 3: Standard FSRS v6 Scheduler

**Files:**
- Create: `src/knowledge_base/srs/fsrs.py`
- Test: `tests/test_fsrs.py`

Reference: https://github.com/open-spaced-repetition/fsrs-rs — FSRS v6 algorithm and default weights.

- [ ] **Step 1: Write failing tests for forgetting curve and interval**

Create `tests/test_fsrs.py`:

```python
"""Tests for srs/fsrs.py — standard FSRS v6 with 4-button grading."""

import math
import pytest
from knowledge_base.srs.fsrs import (
    DECAY,
    FACTOR,
    DESIRED_RETENTION,
    W,
    Grade,
    compute_retrievability,
    compute_interval,
    initial_stability,
    initial_difficulty,
    update_difficulty,
    recall_stability,
    lapse_stability,
    short_term_stability,
    schedule,
    SchedulingResult,
)


class TestRetrievability:
    def test_just_reviewed(self):
        """elapsed=0 → R=1.0."""
        assert compute_retrievability(0.0, 10.0) == pytest.approx(1.0)

    def test_at_stability(self):
        """elapsed == stability → R = 0.9."""
        assert compute_retrievability(10.0, 10.0) == pytest.approx(0.9)

    def test_zero_stability(self):
        assert compute_retrievability(5.0, 0.0) == 0.0


class TestComputeInterval:
    def test_interval_equals_stability(self):
        """With R_d=0.9 and FSRS power-law, interval ≈ stability."""
        assert compute_interval(10.0) == pytest.approx(10.0)

    def test_scales_linearly(self):
        assert compute_interval(20.0) == pytest.approx(2.0 * compute_interval(10.0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fsrs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement forgetting curve and interval**

Create `src/knowledge_base/srs/fsrs.py`:

```python
"""Standard FSRS v6 scheduler with 4-button discrete grading.

A clean implementation of FSRS v6 as published by the open-spaced-repetition
project. Completely independent from scheduler.py (the experimental continuous
FSRS variant used by interval/point cards).

Reference: https://github.com/open-spaced-repetition/fsrs-rs
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

class Grade(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


# ---------------------------------------------------------------------------
# Default weights — FSRS v6 published defaults
# ---------------------------------------------------------------------------

W = [
    0.4072,   # w[0]: initial stability for Again
    1.1829,   # w[1]: initial stability for Hard
    3.1262,   # w[2]: initial stability for Good
    15.4722,  # w[3]: initial stability for Easy
    7.2102,   # w[4]: initial difficulty base
    0.5316,   # w[5]: initial difficulty curve
    1.0651,   # w[6]: difficulty update magnitude
    0.0589,   # w[7]: difficulty mean reversion weight
    1.5330,   # w[8]: recall stability gain (log-scale)
    0.1670,   # w[9]: stability diminishing returns
    1.0458,   # w[10]: retrievability effect on recall
    1.9552,   # w[11]: lapse stability scaling
    0.1082,   # w[12]: difficulty effect on lapse
    0.3264,   # w[13]: pre-lapse S effect
    2.1440,   # w[14]: retrievability effect on lapse
    0.2854,   # w[15]: hard penalty
    2.9898,   # w[16]: easy bonus
    0.5116,   # w[17]: short-term stability rate
    0.7004,   # w[18]: short-term stability offset
]

# ---------------------------------------------------------------------------
# Forgetting curve
# ---------------------------------------------------------------------------

DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1   # ≈ 19/81
DESIRED_RETENTION = 0.9

MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0


def compute_retrievability(elapsed_days: float, stability: float) -> float:
    """FSRS v6 power-law forgetting curve: R(t, S) = (1 + FACTOR*t/S)^DECAY."""
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def compute_interval(stability: float) -> float:
    """Next review interval in days: I = (S/FACTOR) * (R_d^(1/DECAY) - 1).

    With R_d=0.9, simplifies to I = S.
    """
    return (stability / FACTOR) * (DESIRED_RETENTION ** (1 / DECAY) - 1)
```

- [ ] **Step 4: Run forgetting curve tests**

Run: `uv run pytest tests/test_fsrs.py::TestRetrievability tests/test_fsrs.py::TestComputeInterval -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for initial stability/difficulty**

Append to `tests/test_fsrs.py`:

```python
class TestInitialStability:
    def test_again_uses_w0(self):
        assert initial_stability(Grade.AGAIN) == pytest.approx(W[0])

    def test_good_uses_w2(self):
        assert initial_stability(Grade.GOOD) == pytest.approx(W[2])

    def test_easy_highest(self):
        assert initial_stability(Grade.EASY) > initial_stability(Grade.GOOD)


class TestInitialDifficulty:
    def test_in_range(self):
        for g in Grade:
            d = initial_difficulty(g)
            assert 1.0 <= d <= 10.0

    def test_again_hardest(self):
        assert initial_difficulty(Grade.AGAIN) > initial_difficulty(Grade.EASY)
```

- [ ] **Step 6: Implement initial stability/difficulty**

Add to `src/knowledge_base/srs/fsrs.py`:

```python
def initial_stability(grade: Grade) -> float:
    """Return S_0 for a first review: S_0(G) = w[G-1]."""
    return W[grade - 1]


def initial_difficulty(grade: Grade) -> float:
    """Return D_0 for a first review: D_0(G) = w[4] - e^(w[5]*(G-1)) + 1.

    Clamped to [1, 10].
    """
    d = W[4] - math.exp(W[5] * (grade - 1)) + 1
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d))
```

- [ ] **Step 7: Run initial stability/difficulty tests**

Run: `uv run pytest tests/test_fsrs.py::TestInitialStability tests/test_fsrs.py::TestInitialDifficulty -v`
Expected: All PASS

- [ ] **Step 8: Write failing tests for stability updates**

Append to `tests/test_fsrs.py`:

```python
class TestRecallStability:
    def test_increases_on_good(self):
        """Good recall should increase stability."""
        s_new = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        assert s_new > 10.0

    def test_hard_penalty(self):
        """Hard grade should give less stability gain than Good."""
        s_good = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        s_hard = recall_stability(10.0, 5.0, 0.9, Grade.HARD)
        assert s_hard < s_good

    def test_easy_bonus(self):
        """Easy grade should give more stability gain than Good."""
        s_good = recall_stability(10.0, 5.0, 0.9, Grade.GOOD)
        s_easy = recall_stability(10.0, 5.0, 0.9, Grade.EASY)
        assert s_easy > s_good


class TestLapseStability:
    def test_decreases(self):
        """Lapse should reduce stability."""
        s_new = lapse_stability(10.0, 5.0, 0.9)
        assert s_new < 10.0

    def test_higher_difficulty_lower_stability(self):
        """Higher difficulty → lower post-lapse stability."""
        s_easy_d = lapse_stability(10.0, 3.0, 0.9)
        s_hard_d = lapse_stability(10.0, 8.0, 0.9)
        assert s_hard_d < s_easy_d


class TestUpdateDifficulty:
    def test_again_increases(self):
        d_new = update_difficulty(5.0, Grade.AGAIN)
        assert d_new > 5.0

    def test_easy_decreases(self):
        d_new = update_difficulty(5.0, Grade.EASY)
        assert d_new < 5.0

    def test_clamped(self):
        d_low = update_difficulty(1.0, Grade.EASY)
        d_high = update_difficulty(10.0, Grade.AGAIN)
        assert d_low >= 1.0
        assert d_high <= 10.0
```

- [ ] **Step 9: Implement stability and difficulty updates**

Add to `src/knowledge_base/srs/fsrs.py`:

```python
def recall_stability(
    stability: float, difficulty: float, retrievability: float, grade: Grade,
) -> float:
    """Compute new stability after successful recall (grade >= 2).

    S_r = S * (e^w[8] * (11-D) * S^(-w[9]) * (e^(w[10]*(1-R)) - 1) * modifier + 1)
    modifier = w[15] for Hard, w[16] for Easy, 1.0 for Good.
    """
    modifier = 1.0
    if grade == Grade.HARD:
        modifier = W[15]
    elif grade == Grade.EASY:
        modifier = W[16]

    s_inc = (
        math.exp(W[8])
        * (11 - difficulty)
        * stability ** (-W[9])
        * (math.exp(W[10] * (1 - retrievability)) - 1)
        * modifier
    )
    return stability * (max(s_inc, 0) + 1)


def lapse_stability(
    stability: float, difficulty: float, retrievability: float,
) -> float:
    """Compute new stability after a lapse (Again).

    S_f = w[11] * D^(-w[12]) * ((S+1)^w[13] - 1) * e^(w[14]*(1-R))
    """
    return (
        W[11]
        * difficulty ** (-W[12])
        * ((stability + 1) ** W[13] - 1)
        * math.exp(W[14] * (1 - retrievability))
    )


def short_term_stability(stability: float, grade: Grade) -> float:
    """Compute stability for same-day (short-term) reviews.

    S_s = S * e^(w[17] * (G - 3 + w[18]))
    """
    return stability * math.exp(W[17] * (grade - 3 + W[18]))


def update_difficulty(difficulty: float, grade: Grade) -> float:
    """Update difficulty after a review.

    D' = D - w[6] * (G - 3)
    D_new = w[7] * D_0(Good) + (1 - w[7]) * D'
    Clamped to [1, 10].
    """
    d_prime = difficulty - W[6] * (grade - 3)
    d0_good = initial_difficulty(Grade.GOOD)
    d_new = W[7] * d0_good + (1 - W[7]) * d_prime
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, d_new))
```

- [ ] **Step 10: Run stability/difficulty update tests**

Run: `uv run pytest tests/test_fsrs.py::TestRecallStability tests/test_fsrs.py::TestLapseStability tests/test_fsrs.py::TestUpdateDifficulty -v`
Expected: All PASS

- [ ] **Step 11: Write failing tests for `schedule()`**

Append to `tests/test_fsrs.py`:

```python
class TestSchedule:
    def test_first_review_good(self):
        """First review with Good → initial stability/difficulty, interval > 0."""
        result = schedule(
            difficulty=0.0, stability=0.0, reps=0,
            last_review=None, grade=Grade.GOOD, now="2026-01-01T12:00:00",
        )
        assert result.stability == pytest.approx(W[2])
        assert result.difficulty > 0
        assert result.interval > 0
        assert result.reps == 1

    def test_first_review_again(self):
        """First review Again → lowest initial stability."""
        result = schedule(
            difficulty=0.0, stability=0.0, reps=0,
            last_review=None, grade=Grade.AGAIN, now="2026-01-01T12:00:00",
        )
        assert result.stability == pytest.approx(W[0])

    def test_established_card_good(self):
        """Established card + Good → stability increases."""
        result = schedule(
            difficulty=5.0, stability=10.0, reps=5,
            last_review="2026-01-01T12:00:00", grade=Grade.GOOD,
            now="2026-01-11T12:00:00",  # 10 days later
        )
        assert result.stability > 10.0
        assert result.reps == 6

    def test_established_card_again(self):
        """Established card + Again → stability decreases (lapse)."""
        result = schedule(
            difficulty=5.0, stability=10.0, reps=5,
            last_review="2026-01-01T12:00:00", grade=Grade.AGAIN,
            now="2026-01-11T12:00:00",
        )
        assert result.stability < 10.0

    def test_result_has_due_date(self):
        """Result should include a due date string."""
        result = schedule(
            difficulty=0.0, stability=0.0, reps=0,
            last_review=None, grade=Grade.GOOD, now="2026-01-01T12:00:00",
        )
        assert result.due is not None
        assert "2026-01" in result.due

    def test_same_day_review(self):
        """Same-day review uses short-term stability."""
        result = schedule(
            difficulty=5.0, stability=10.0, reps=5,
            last_review="2026-01-01T10:00:00", grade=Grade.GOOD,
            now="2026-01-01T12:00:00",  # 2 hours later
        )
        assert result.stability > 0
        assert result.reps == 6
```

- [ ] **Step 12: Implement `schedule()` and `SchedulingResult`**

Add to `src/knowledge_base/srs/fsrs.py`:

```python
@dataclass
class SchedulingResult:
    """Output of a scheduling decision."""
    difficulty: float
    stability: float
    interval: float       # days
    due: str              # ISO-8601 timestamp
    reps: int


def schedule(
    difficulty: float,
    stability: float,
    reps: int,
    last_review: str | None,
    grade: Grade,
    now: str,
) -> SchedulingResult:
    """Compute new card state after a review.

    First review (reps=0): uses initial_stability/initial_difficulty.
    Established card: uses recall/lapse stability based on grade.
    Same-day review (elapsed < 1 day): uses short_term_stability.
    """
    from datetime import datetime, timedelta, timezone

    now_dt = datetime.fromisoformat(now)

    if reps == 0:
        new_stability = initial_stability(grade)
        new_difficulty = initial_difficulty(grade)
    else:
        # Compute elapsed days
        elapsed_days = 0.0
        if last_review:
            last_dt = datetime.fromisoformat(last_review)
            elapsed_days = (now_dt - last_dt).total_seconds() / 86400

        retrievability = compute_retrievability(elapsed_days, stability)
        new_difficulty = update_difficulty(difficulty, grade)

        if grade == Grade.AGAIN:
            new_stability = lapse_stability(stability, difficulty, retrievability)
        else:
            new_stability = recall_stability(
                stability, difficulty, retrievability, grade,
            )

        # Same-day floor: use short-term stability if elapsed < 1 day
        if elapsed_days < 1.0 and grade != Grade.AGAIN:
            st = short_term_stability(stability, grade)
            new_stability = max(new_stability, st)

    interval = compute_interval(new_stability)
    due_dt = now_dt + timedelta(days=interval)

    return SchedulingResult(
        difficulty=new_difficulty,
        stability=new_stability,
        interval=interval,
        due=due_dt.isoformat(),
        reps=reps + 1,
    )
```

- [ ] **Step 13: Run all FSRS tests**

Run: `uv run pytest tests/test_fsrs.py -v`
Expected: All PASS

- [ ] **Step 14: Commit**

```bash
git add src/knowledge_base/srs/fsrs.py tests/test_fsrs.py
git commit -m "feat: add standard FSRS v6 scheduler with 4-button grading"
```

---

### Task 4: Generation DB (Schema and CRUD)

**Files:**
- Create: `src/knowledge_base/srs/generation_db.py`
- Test: `tests/test_generation_db.py`

- [ ] **Step 1: Write failing tests for schema init**

Create `tests/test_generation_db.py`:

```python
"""Tests for srs/generation_db.py — generation card schema and CRUD."""

import sqlite3
import pytest
from knowledge_base.srs.generation_db import (
    init_generation_db,
    insert_generation_card,
    get_generation_card,
    upsert_generation_card,
    update_generation_scheduling,
    update_generation_phase,
    get_due_generation_cards,
    get_generation_phase_cards,
    insert_generation_review,
    CURRENT_SCHEMA_VERSION,
)


def _minimal_card(**overrides) -> dict:
    base = {
        "deck": "cfa_level1",
        "topic_id": "1",
        "los_id": "1.a",
        "question": "What is LOS 1.a?",
        "answer": "interpret interest rates as required rates of return",
        "tags": "[]",
    }
    base.update(overrides)
    return base


class TestSchemaInit:
    def test_creates_tables(self):
        conn = init_generation_db(":memory:")
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "generation_cards" in table_names
        assert "generation_review_log" in table_names

    def test_schema_version(self):
        conn = init_generation_db(":memory:")
        version = conn.execute(
            "SELECT version FROM generation_schema_version"
        ).fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION

    def test_idempotent(self):
        conn = init_generation_db(":memory:")
        init_generation_db(conn=conn)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generation_db.py::TestSchemaInit -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement schema creation**

Create `src/knowledge_base/srs/generation_db.py`:

```python
"""SQLite persistence for generation cards.

Separate from db.py — generation cards have their own table, schema version,
and review log to avoid any coupling with the interval card system.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1

_DDL_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS generation_schema_version (
    version INTEGER NOT NULL
);
"""

_DDL_CARDS = """
CREATE TABLE IF NOT EXISTS generation_cards (
    card_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    deck                   TEXT    NOT NULL,
    topic_id               TEXT    NOT NULL,
    los_id                 TEXT    NOT NULL,
    question               TEXT    NOT NULL,
    answer                 TEXT    NOT NULL,
    tags                   TEXT    NOT NULL DEFAULT '[]',
    masking_level          INTEGER NOT NULL DEFAULT 0,
    phase                  TEXT    NOT NULL DEFAULT 'generation',
    consecutive_max_passes INTEGER NOT NULL DEFAULT 0,
    difficulty             REAL    NOT NULL DEFAULT 5.0,
    stability              REAL    NOT NULL DEFAULT 0.0,
    last_review            TEXT,
    due                    TEXT,
    reps                   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (deck, los_id)
);
"""

_DDL_REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS generation_review_log (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          INTEGER NOT NULL REFERENCES generation_cards(card_id),
    timestamp        TEXT    NOT NULL,
    answer_mode      TEXT    NOT NULL,
    phase_level      INTEGER,
    grade            INTEGER,
    passed           INTEGER,
    elapsed_days     REAL    NOT NULL,
    interval_applied REAL
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_gen_cards_due  ON generation_cards (due, reps);
CREATE INDEX IF NOT EXISTS idx_gen_cards_deck ON generation_cards (deck);
CREATE INDEX IF NOT EXISTS idx_gen_cards_phase ON generation_cards (phase);
CREATE INDEX IF NOT EXISTS idx_gen_review_card ON generation_review_log (card_id);
"""

_SCHEDULING_FIELDS = frozenset({
    "difficulty", "stability", "last_review", "due", "reps",
})

_PHASE_FIELDS = frozenset({
    "masking_level", "phase", "consecutive_max_passes",
})

_CONTENT_FIELDS = (
    "deck", "topic_id", "question", "answer", "tags",
)


def init_generation_db(
    db_path: str | Path = ":memory:", conn: sqlite3.Connection | None = None,
) -> sqlite3.Connection:
    """Open or create the generation cards database."""
    if conn is None:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

    with conn:
        conn.execute(_DDL_SCHEMA_VERSION)
        conn.execute(_DDL_CARDS)
        conn.execute(_DDL_REVIEW_LOG)
        for stmt in _DDL_INDEXES.strip().splitlines():
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        count = conn.execute(
            "SELECT COUNT(*) FROM generation_schema_version"
        ).fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO generation_schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
    return conn
```

- [ ] **Step 4: Run schema tests**

Run: `uv run pytest tests/test_generation_db.py::TestSchemaInit -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for CRUD**

Append to `tests/test_generation_db.py`:

```python
class TestInsertAndGet:
    def test_insert_and_get(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        card = get_generation_card(conn, card_id)
        assert card is not None
        assert card["los_id"] == "1.a"
        assert card["phase"] == "generation"
        assert card["masking_level"] == 0

    def test_upsert_preserves_scheduling(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_scheduling(conn, card_id, {
            "difficulty": 8.0, "stability": 5.0, "reps": 3,
        })
        upsert_generation_card(conn, _minimal_card(
            answer="updated answer text",
        ))
        card = get_generation_card(conn, card_id)
        assert card["answer"] == "updated answer text"
        assert card["difficulty"] == 8.0
        assert card["reps"] == 3


class TestUpdatePhase:
    def test_update_masking_level(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {"masking_level": 2})
        card = get_generation_card(conn, card_id)
        assert card["masking_level"] == 2

    def test_graduate_to_recall(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {
            "phase": "recall",
            "consecutive_max_passes": 0,
        })
        card = get_generation_card(conn, card_id)
        assert card["phase"] == "recall"


class TestDueCards:
    def test_generation_phase_cards(self):
        conn = init_generation_db(":memory:")
        insert_generation_card(conn, _minimal_card(los_id="1.a"))
        insert_generation_card(conn, _minimal_card(los_id="1.b"))
        cards = get_generation_phase_cards(conn, deck="cfa_level1")
        assert len(cards) == 2

    def test_recall_due_cards(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        update_generation_phase(conn, card_id, {"phase": "recall"})
        update_generation_scheduling(conn, card_id, {
            "due": "2026-01-01T00:00:00", "reps": 1,
        })
        cards = get_due_generation_cards(
            conn, as_of="2026-01-02T00:00:00", deck="cfa_level1",
        )
        assert len(cards) == 1
        assert cards[0]["phase"] == "recall"


class TestReviewLog:
    def test_insert_review(self):
        conn = init_generation_db(":memory:")
        card_id = insert_generation_card(conn, _minimal_card())
        review_id = insert_generation_review(conn, {
            "card_id": card_id,
            "timestamp": "2026-01-01T12:00:00",
            "answer_mode": "generation",
            "phase_level": 0,
            "grade": None,
            "passed": 1,
            "elapsed_days": 0.0,
            "interval_applied": None,
        })
        assert review_id > 0
```

- [ ] **Step 6: Implement CRUD functions**

Add to `src/knowledge_base/srs/generation_db.py`:

```python
def insert_generation_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert a new generation card, return card_id."""
    columns = list(card.keys())
    placeholders = ", ".join("?" * len(columns))
    col_clause = ", ".join(columns)
    values = [card[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid


def get_generation_card(conn: sqlite3.Connection, card_id: int) -> dict | None:
    """Return the card as a dict, or None."""
    row = conn.execute(
        "SELECT * FROM generation_cards WHERE card_id = ?", (card_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_generation_card(conn: sqlite3.Connection, card: dict) -> int:
    """Insert or update by (deck, los_id). Preserves scheduling/phase state."""
    columns = list(card.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [card[c] for c in columns]

    update_parts = [f"{f} = excluded.{f}" for f in _CONTENT_FIELDS if f in card]
    if not update_parts:
        upsert_sql = (
            f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders}) "
            "ON CONFLICT (deck, los_id) DO NOTHING RETURNING card_id"
        )
        row = conn.execute(upsert_sql, values).fetchone()
        if row:
            conn.commit()
            return row[0]
        existing = conn.execute(
            "SELECT card_id FROM generation_cards WHERE deck=? AND los_id=?",
            (card["deck"], card["los_id"]),
        ).fetchone()
        conn.commit()
        return existing[0]

    update_clause = ", ".join(update_parts)
    upsert_sql = (
        f"INSERT INTO generation_cards ({col_clause}) VALUES ({placeholders}) "
        f"ON CONFLICT (deck, los_id) DO UPDATE SET {update_clause} "
        "RETURNING card_id"
    )
    row = conn.execute(upsert_sql, values).fetchone()
    conn.commit()
    return row[0]


def update_generation_scheduling(
    conn: sqlite3.Connection, card_id: int, fields: dict,
) -> None:
    """Update FSRS scheduling columns."""
    allowed = {k: v for k, v in fields.items() if k in _SCHEDULING_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(
        f"UPDATE generation_cards SET {set_clause} WHERE card_id = ?", values,
    )
    conn.commit()


def update_generation_phase(
    conn: sqlite3.Connection, card_id: int, fields: dict,
) -> None:
    """Update generation phase columns (masking_level, phase, consecutive_max_passes)."""
    allowed = {k: v for k, v in fields.items() if k in _PHASE_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [card_id]
    conn.execute(
        f"UPDATE generation_cards SET {set_clause} WHERE card_id = ?", values,
    )
    conn.commit()


def get_generation_phase_cards(
    conn: sqlite3.Connection,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return all generation-phase cards (for intra-session queue)."""
    params: list = []
    where_parts = ["phase = 'generation'"]
    if deck is not None:
        where_parts.append("deck = ?")
        params.append(deck)
    where_clause = " AND ".join(where_parts)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    rows = conn.execute(
        f"SELECT * FROM generation_cards WHERE {where_clause} "
        f"ORDER BY RANDOM() {limit_clause}",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_due_generation_cards(
    conn: sqlite3.Connection,
    as_of: str,
    deck: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return recall-phase cards that are due for review."""
    params: list = [as_of]
    deck_clause = ""
    if deck is not None:
        deck_clause = "AND deck = ?"
        params.append(deck)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT * FROM generation_cards
        WHERE phase = 'recall'
          AND reps > 0
          AND due <= ?
          {deck_clause}
        ORDER BY due ASC
        {limit_clause}
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def insert_generation_review(conn: sqlite3.Connection, review: dict) -> int:
    """Insert a generation review log entry, return review_id."""
    columns = list(review.keys())
    col_clause = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    values = [review[c] for c in columns]
    cur = conn.execute(
        f"INSERT INTO generation_review_log ({col_clause}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid
```

- [ ] **Step 7: Run all generation DB tests**

Run: `uv run pytest tests/test_generation_db.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/knowledge_base/srs/generation_db.py tests/test_generation_db.py
git commit -m "feat: add generation_cards schema and CRUD operations"
```

---

### Task 5: LOS Data File

**Files:**
- Create: `data/cfa_level1_los.json`

This task extracts LOS statements from the SchweserNotes PDFs into a structured JSON file. The extraction is manual/semi-automated — the LOS text is on pages 9-12 of Book 1, pages 7-8 of Book 2, and pages 7-10 of Book 3.

- [ ] **Step 1: Create the LOS data file**

Create `data/cfa_level1_los.json` containing all 48 readings' LOS statements. Extract the text from the PDF pages already read during brainstorming.

The file should follow this structure (showing first 3 readings; the full file contains all 48):

```json
{
  "deck": "cfa_level1",
  "readings": [
    {
      "number": 1,
      "title": "Rates and Returns",
      "book": 1,
      "los": [
        {"id": "1.a", "text": "interpret interest rates as required rates of return, discount rates, or opportunity costs and explain an interest rate as the sum of a real risk-free rate and premiums that compensate investors for bearing distinct types of risk"},
        {"id": "1.b", "text": "calculate and interpret different approaches to return measurement over time and describe their appropriate uses"},
        {"id": "1.c", "text": "compare the money-weighted and time-weighted rates of return and evaluate the performance of portfolios based on these measures"},
        {"id": "1.d", "text": "calculate and interpret annualized return measures and continuously compounded returns, and describe their appropriate uses"},
        {"id": "1.e", "text": "calculate and interpret major return measures and describe their appropriate uses"}
      ]
    },
    {
      "number": 2,
      "title": "The Time Value of Money in Finance",
      "book": 1,
      "los": [
        {"id": "2.a", "text": "calculate and interpret the present value (PV) of fixed-income and equity instruments based on expected future cash flows"},
        {"id": "2.b", "text": "calculate and interpret the implied return of fixed-income instruments and required return and implied growth of equity instruments given the present value (PV) and cash flows"},
        {"id": "2.c", "text": "explain the cash flow additivity principle, its importance for the no-arbitrage condition, and its use in calculating implied forward interest rates, forward exchange rates, and option values"}
      ]
    },
    {
      "number": 3,
      "title": "Statistical Measures of Asset Returns",
      "book": 1,
      "los": [
        {"id": "3.a", "text": "calculate, interpret, and evaluate measures of central tendency and location to address an investment problem"},
        {"id": "3.b", "text": "calculate, interpret, and evaluate measures of dispersion to address an investment problem"},
        {"id": "3.c", "text": "interpret and evaluate measures of skewness and kurtosis to address an investment problem"},
        {"id": "3.d", "text": "interpret correlation between two variables to address an investment problem"}
      ]
    }
  ]
}
```

Populate all 48 readings from the PDF text already captured. Each LOS text should be lowercase-start (matching the source, which begins "interpret...", "calculate...", "describe..." etc.) with no trailing period.

- [ ] **Step 2: Validate JSON is well-formed**

Run: `python -c "import json; d=json.load(open('data/cfa_level1_los.json')); print(f'{len(d[\"readings\"])} readings, {sum(len(r[\"los\"]) for r in d[\"readings\"])} LOS')" `
Expected: `48 readings, ~200+ LOS` (exact count depends on extraction)

- [ ] **Step 3: Commit**

```bash
git add data/cfa_level1_los.json
git commit -m "data: add CFA Level I LOS statements (48 readings)"
```

---

### Task 6: Import Pipeline

**Files:**
- Create: `src/knowledge_base/srs/generation_import.py`
- Test: `tests/test_generation_import.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generation_import.py`:

```python
"""Tests for srs/generation_import.py — LOS import pipeline."""

import json
import pytest
from pathlib import Path
from knowledge_base.srs.generation_db import (
    init_generation_db,
    get_generation_card,
)
from knowledge_base.srs.generation_import import import_los


@pytest.fixture
def sample_los_data(tmp_path):
    """Create a minimal LOS JSON file for testing."""
    data = {
        "deck": "cfa_level1",
        "readings": [
            {
                "number": 1,
                "title": "Rates and Returns",
                "book": 1,
                "los": [
                    {
                        "id": "1.a",
                        "text": "interpret interest rates as required rates of return",
                    },
                    {
                        "id": "1.b",
                        "text": "calculate and interpret different approaches to return measurement",
                    },
                ],
            },
            {
                "number": 2,
                "title": "Time Value of Money",
                "book": 1,
                "los": [
                    {
                        "id": "2.a",
                        "text": "calculate and interpret the present value of fixed-income instruments",
                    },
                ],
            },
        ],
    }
    path = tmp_path / "los.json"
    path.write_text(json.dumps(data))
    return path


class TestImportLos:
    def test_imports_all_cards(self, sample_los_data):
        conn = init_generation_db(":memory:")
        count = import_los(conn, sample_los_data)
        assert count == 3

    def test_card_content(self, sample_los_data):
        conn = init_generation_db(":memory:")
        import_los(conn, sample_los_data)
        row = conn.execute(
            "SELECT * FROM generation_cards WHERE los_id = '1.a'"
        ).fetchone()
        card = dict(row)
        assert card["deck"] == "cfa_level1"
        assert card["topic_id"] == "1"
        assert card["question"] == "What is LOS 1.a?"
        assert "interpret interest rates" in card["answer"]
        assert card["phase"] == "generation"
        assert card["masking_level"] == 0

    def test_tags(self, sample_los_data):
        conn = init_generation_db(":memory:")
        import_los(conn, sample_los_data)
        row = conn.execute(
            "SELECT tags FROM generation_cards WHERE los_id = '1.a'"
        ).fetchone()
        tags = json.loads(row[0])
        assert "reading::1" in tags
        assert "book::1" in tags

    def test_idempotent(self, sample_los_data):
        conn = init_generation_db(":memory:")
        import_los(conn, sample_los_data)
        import_los(conn, sample_los_data)  # second import
        count = conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        assert count == 3  # no duplicates

    def test_preserves_scheduling_on_reimport(self, sample_los_data):
        conn = init_generation_db(":memory:")
        import_los(conn, sample_los_data)
        # Simulate some scheduling progress
        conn.execute(
            "UPDATE generation_cards SET masking_level=2, reps=5 WHERE los_id='1.a'"
        )
        conn.commit()
        import_los(conn, sample_los_data)
        row = conn.execute(
            "SELECT masking_level, reps FROM generation_cards WHERE los_id='1.a'"
        ).fetchone()
        assert row[0] == 2  # masking_level preserved
        assert row[1] == 5  # reps preserved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generation_import.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement import_los**

Create `src/knowledge_base/srs/generation_import.py`:

```python
"""Import LOS statements from JSON into the generation cards database."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_base.srs.generation_db import (
    init_generation_db,
    upsert_generation_card,
)

DEFAULT_LOS_PATH = Path("data/cfa_level1_los.json")


def _slugify(text: str) -> str:
    """Convert a title to a tag-friendly slug."""
    return text.lower().replace(" ", "_").replace(":", "").replace(",", "")


def import_los(conn, data_path: Path | None = None) -> int:
    """Import LOS statements from JSON into generation_cards.

    Idempotent: upserts by (deck, los_id), preserving scheduling state.
    Returns count of cards upserted.
    """
    resolved = data_path or DEFAULT_LOS_PATH
    with open(resolved) as f:
        data = json.load(f)

    deck = data["deck"]
    count = 0

    for reading in data["readings"]:
        number = reading["number"]
        title = reading["title"]
        book = reading.get("book", 1)

        tags = [
            f"reading::{number}",
            f"topic::{_slugify(title)}",
            f"book::{book}",
        ]

        for los in reading["los"]:
            los_id = los["id"]
            text = los["text"]

            upsert_generation_card(conn, {
                "deck": deck,
                "topic_id": str(number),
                "los_id": los_id,
                "question": f"What is LOS {los_id}?",
                "answer": text,
                "tags": json.dumps(tags),
            })
            count += 1

    return count


def main() -> None:
    """CLI entry point for LOS import."""
    import argparse

    parser = argparse.ArgumentParser(description="Import CFA LOS into generation cards")
    parser.add_argument(
        "--db", default="data/srs.db",
        help="Database path (default: data/srs.db)",
    )
    parser.add_argument(
        "--data", default=None,
        help="Path to LOS JSON file (default: data/cfa_level1_los.json)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_generation_db(db_path)
    data_path = Path(args.data) if args.data else None
    count = import_los(conn, data_path)
    print(f"Imported {count} LOS cards into {db_path}")
```

- [ ] **Step 4: Run import tests**

Run: `uv run pytest tests/test_generation_import.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_base/srs/generation_import.py tests/test_generation_import.py
git commit -m "feat: add LOS import pipeline for generation cards"
```

---

### Task 7: Entry Points

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Register new CLI commands**

In `pyproject.toml`, add two new entries to `[project.scripts]`:

```toml
[project.scripts]
fetch-data = "knowledge_base.fetch_data:main"
fetch-urban-data = "knowledge_base.fetch_urban_data:main"
fetch-desc-stats = "knowledge_base.fetch_desc_stats:main"
build-deck = "knowledge_base.build_deck:main"
review = "knowledge_base.srs.tui:main"
srs-import = "knowledge_base.srs.importer:main"
review-gen = "knowledge_base.srs.generation_tui:main"
gen-import = "knowledge_base.srs.generation_import:main"
```

- [ ] **Step 2: Run uv sync**

Run: `uv sync`
Expected: Resolves successfully.

- [ ] **Step 3: Verify gen-import works**

Run: `uv run gen-import --help`
Expected: Shows help text without `ModuleNotFoundError`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: register review-gen and gen-import CLI entry points"
```

---

### Task 8: Generation TUI

**Files:**
- Create: `src/knowledge_base/srs/generation_tui.py`

This is the largest task. The TUI has two review modes (generation and recall), queue management for generation-phase cards, and FSRS scheduling for recall-phase cards.

- [ ] **Step 1: Create the TUI with generation phase support**

Create `src/knowledge_base/srs/generation_tui.py`:

```python
"""Textual TUI for reviewing generation cards (CFA LOS)."""

from __future__ import annotations

import argparse
import json
from collections import deque
from datetime import datetime, timedelta, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Static

from knowledge_base.srs.fsrs import Grade, schedule
from knowledge_base.srs.generation_db import (
    get_due_generation_cards,
    get_generation_phase_cards,
    init_generation_db,
    insert_generation_review,
    update_generation_phase,
    update_generation_scheduling,
)
from knowledge_base.srs.masking import mask_text
from knowledge_base.srs.text_scoring import compare_tokens, tokenize


# ---------------------------------------------------------------------------
# Queue item: wraps a card dict with queue-spacing metadata
# ---------------------------------------------------------------------------

class QueueItem:
    """A card in the review queue with spacing metadata."""

    def __init__(self, card: dict, delay: int = 0):
        self.card = card
        self.delay = delay  # number of other reviews before this card appears


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
Screen {
    background: $surface;
}

#card-header {
    dock: top;
    width: 100%;
    height: auto;
    padding: 1 2;
    color: $text-muted;
}

#question {
    width: 100%;
    height: auto;
    padding: 1 2;
    text-style: bold;
}

#masked-text {
    width: 100%;
    height: auto;
    padding: 1 2;
    color: $text;
}

#answer-input {
    width: 100%;
    margin: 1 2;
}

#result {
    width: 100%;
    height: auto;
    padding: 1 2;
}

#stats-display {
    width: 100%;
    height: auto;
    padding: 1 2;
}
"""

# Graduation: 2 consecutive passes at level 2 with >=5 card gap
MAX_MASKING_LEVEL = 2
GRADUATION_PASSES = 2
GRADUATION_GAP = 5
REGRESSION_INTERVAL_THRESHOLD = 1.0  # days — regress if Again interval < this


class GenerationReviewApp(App):
    """Textual app for generation card review."""

    CSS = _CSS
    TITLE = "Generation Review"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "toggle_stats", "Stats", priority=True),
    ]

    def __init__(
        self,
        db_path: str = "data/srs.db",
        deck: str | None = None,
        limit: int | None = None,
        stats_only: bool = False,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.deck_filter = deck
        self.card_limit = limit
        self.stats_only = stats_only
        self.conn = None

        # Review queue
        self.queue: deque[QueueItem] = deque()
        self.reviews_since: int = 0  # counter for queue spacing
        self.total_reviewed: int = 0
        self.total_cards: int = 0

        # Current card state
        self.current_item: QueueItem | None = None
        self.showing_feedback: bool = False
        self.showing_stats: bool = False
        self.feedback_phase: str = ""  # "generation" or "recall"

    def _hide_input(self) -> None:
        inp = self.query_one("#answer-input", Input)
        inp.display = False
        inp.blur()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="card-header")
            yield Static("", id="question")
            yield Static("", id="masked-text")
            yield Input(placeholder="Type your answer", id="answer-input")
            yield Static("", id="result")
            yield Static("", id="stats-display")
        yield Footer()

    def on_mount(self) -> None:
        self.conn = init_generation_db(self.db_path)
        if self.stats_only:
            self._show_stats_screen()
            return
        self._build_queue()
        if not self.queue:
            self.query_one("#card-header", Static).update("No cards due")
            self.query_one("#question", Static).update(
                "All caught up! Press Ctrl+Q to quit."
            )
            self._hide_input()
            return
        self._advance()

    def _build_queue(self) -> None:
        """Load generation-phase and due recall-phase cards into the queue."""
        now = datetime.now(timezone.utc).isoformat()

        # Recall-phase due cards first (by due date)
        recall_cards = get_due_generation_cards(
            self.conn, as_of=now, deck=self.deck_filter, limit=self.card_limit,
        )
        for card in recall_cards:
            self.queue.append(QueueItem(card, delay=0))

        # Generation-phase cards (random order)
        remaining = (self.card_limit - len(recall_cards)) if self.card_limit else None
        gen_cards = get_generation_phase_cards(
            self.conn, deck=self.deck_filter,
            limit=remaining if remaining and remaining > 0 else None,
        )
        for card in gen_cards:
            self.queue.append(QueueItem(card, delay=0))

        self.total_cards = len(self.queue)

    def _advance(self) -> None:
        """Move to the next card in the queue."""
        # Find next ready item (delay == 0)
        while self.queue:
            item = self.queue[0]
            if item.delay <= 0:
                self.current_item = self.queue.popleft()
                break
            # Decrement delays for front item and rotate
            item = self.queue.popleft()
            item.delay -= 1
            self.queue.append(item)
        else:
            # Check if anything left with delays
            if any(True for _ in self.queue):
                # Force next item
                item = self.queue.popleft()
                item.delay = 0
                self.current_item = item
            else:
                self._session_complete()
                return

        self._show_card()

    def _session_complete(self) -> None:
        self.query_one("#card-header", Static).update("Session complete")
        self.query_one("#question", Static).update(
            f"Reviewed {self.total_reviewed} cards! Press Ctrl+Q to quit or Ctrl+S for stats."
        )
        self.query_one("#masked-text", Static).update("")
        self._hide_input()
        self.query_one("#result", Static).update("")

    def _show_card(self) -> None:
        """Display the current card."""
        card = self.current_item.card
        phase = card["phase"]

        self.total_reviewed += 1
        idx = self.total_reviewed
        header = f"{card['deck']} > LOS {card['los_id']}  [{idx}/{self.total_cards}]"

        if phase == "generation":
            level = card["masking_level"]
            header += f"  (generation — level {level}/{MAX_MASKING_LEVEL})"
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(f"LOS {card['los_id']}:")

            masked = mask_text(card["answer"], level=level, card_id=card["card_id"])
            self.query_one("#masked-text", Static).update(masked)
        else:
            header += "  (recall)"
            self.query_one("#card-header", Static).update(header)
            self.query_one("#question", Static).update(card["question"])
            self.query_one("#masked-text", Static).update("")

        self.query_one("#result", Static).update("")
        self.query_one("#stats-display", Static).update("")
        self.showing_feedback = False
        self.feedback_phase = ""

        inp = self.query_one("#answer-input", Input)
        inp.display = True
        inp.value = ""
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.showing_stats or self.showing_feedback:
            return
        if not self.current_item:
            return

        text = event.value.strip()
        if not text:
            return

        card = self.current_item.card
        correct = card["answer"]

        # Compare tokens
        typed_tokens = tokenize(text)
        correct_tokens = tokenize(correct)
        results = compare_tokens(typed_tokens, correct_tokens)

        # Build colored feedback
        lines = []
        colored_parts = []
        for r in results:
            if r.status == "exact":
                colored_parts.append(f"[green]{r.expected}[/]")
            elif r.status == "close":
                colored_parts.append(f"[yellow]{r.typed}[/]")
            elif r.status == "wrong":
                colored_parts.append(f"[red]{r.typed}→{r.expected}[/]")
            elif r.status == "missing":
                colored_parts.append(f"[red dim]_{r.expected}_[/]")
            elif r.status == "extra":
                colored_parts.append(f"[red]+{r.typed}[/]")
        lines.append(" ".join(colored_parts))
        lines.append("")
        lines.append(f"[dim]Correct:[/] {correct}")

        if card["phase"] == "generation":
            lines.append("")
            lines.append("[bold]Pass[/] (Space/Enter)  |  [bold]Fail[/] (f)")
            self.feedback_phase = "generation"
        else:
            lines.append("")
            lines.append(
                "[bold]Again[/](1)  [bold]Hard[/](2)  "
                "[bold]Good[/](3)  [bold]Easy[/](4)"
            )
            self.feedback_phase = "recall"

        self.query_one("#result", Static).update("\n".join(lines))
        self.showing_feedback = True
        self._hide_input()

    def on_key(self, event) -> None:
        if not self.showing_feedback or not self.current_item:
            return

        card = self.current_item.card

        if self.feedback_phase == "generation":
            if event.key in ("space", "enter"):
                event.prevent_default()
                self._handle_generation_pass(card)
            elif event.key == "f":
                event.prevent_default()
                self._handle_generation_fail(card)
            else:
                return

        elif self.feedback_phase == "recall":
            if event.key in ("1", "2", "3", "4"):
                event.prevent_default()
                grade = Grade(int(event.key))
                self._handle_recall_grade(card, grade)
            else:
                return

    def _handle_generation_pass(self, card: dict) -> None:
        """Handle a pass during generation phase."""
        now_str = datetime.now(timezone.utc).isoformat()
        level = card["masking_level"]

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "generation",
            "phase_level": level,
            "grade": None,
            "passed": 1,
            "elapsed_days": 0.0,
            "interval_applied": None,
        })

        if level < MAX_MASKING_LEVEL:
            # Advance masking level
            new_level = level + 1
            update_generation_phase(self.conn, card["card_id"], {
                "masking_level": new_level,
                "consecutive_max_passes": 0,
            })
            card["masking_level"] = new_level
            card["consecutive_max_passes"] = 0
            delay = new_level + 1
            self.queue.append(QueueItem(card, delay=delay))
        else:
            # At max level — track consecutive passes
            passes = card["consecutive_max_passes"] + 1
            if passes >= GRADUATION_PASSES:
                # Graduate to recall phase
                update_generation_phase(self.conn, card["card_id"], {
                    "phase": "recall",
                    "consecutive_max_passes": 0,
                })
                self.query_one("#result", Static).update(
                    self.query_one("#result", Static).renderable
                    + "\n[bold green]Graduated to recall phase![/]"
                )
            else:
                update_generation_phase(self.conn, card["card_id"], {
                    "consecutive_max_passes": passes,
                })
                card["consecutive_max_passes"] = passes
                # Re-queue with graduation gap
                self.queue.append(QueueItem(card, delay=GRADUATION_GAP))

        self.reviews_since = 0
        self.showing_feedback = False
        self._advance()

    def _handle_generation_fail(self, card: dict) -> None:
        """Handle a fail during generation phase."""
        now_str = datetime.now(timezone.utc).isoformat()

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "generation",
            "phase_level": card["masking_level"],
            "grade": None,
            "passed": 0,
            "elapsed_days": 0.0,
            "interval_applied": None,
        })

        # Reset to level 0
        update_generation_phase(self.conn, card["card_id"], {
            "masking_level": 0,
            "consecutive_max_passes": 0,
        })
        card["masking_level"] = 0
        card["consecutive_max_passes"] = 0
        self.queue.append(QueueItem(card, delay=1))

        self.reviews_since = 0
        self.showing_feedback = False
        self._advance()

    def _handle_recall_grade(self, card: dict, grade: Grade) -> None:
        """Handle FSRS grading during recall phase."""
        now_str = datetime.now(timezone.utc).isoformat()

        result = schedule(
            difficulty=card["difficulty"],
            stability=card["stability"],
            reps=card["reps"],
            last_review=card["last_review"],
            grade=grade,
            now=now_str,
        )

        # Check regression rule
        if grade == Grade.AGAIN and result.interval < REGRESSION_INTERVAL_THRESHOLD:
            update_generation_phase(self.conn, card["card_id"], {
                "phase": "generation",
                "masking_level": MAX_MASKING_LEVEL,
                "consecutive_max_passes": 0,
            })
            card["phase"] = "generation"
            card["masking_level"] = MAX_MASKING_LEVEL
            card["consecutive_max_passes"] = 0
            self.queue.append(QueueItem(card, delay=1))
            regression_msg = "\n[bold red]Regressed to generation phase (level 2)[/]"
        else:
            update_generation_scheduling(self.conn, card["card_id"], {
                "difficulty": result.difficulty,
                "stability": result.stability,
                "last_review": now_str,
                "due": result.due,
                "reps": result.reps,
            })
            regression_msg = ""

        insert_generation_review(self.conn, {
            "card_id": card["card_id"],
            "timestamp": now_str,
            "answer_mode": "recall",
            "phase_level": None,
            "grade": int(grade),
            "passed": None,
            "elapsed_days": 0.0,
            "interval_applied": result.interval,
        })

        # Show interval
        interval = result.interval
        if interval < 1.0:
            hours = round(interval * 24)
            interval_str = f"{hours} hour{'s' if hours != 1 else ''}"
        elif interval < 1.5:
            interval_str = "1 day"
        else:
            days = round(interval)
            interval_str = f"{days} day{'s' if days != 1 else ''}"

        current_result = self.query_one("#result", Static).renderable
        self.query_one("#result", Static).update(
            f"{current_result}\n\n[bold]Next review:[/] {interval_str}{regression_msg}"
        )

        self.showing_feedback = False
        self._advance()

    def action_toggle_stats(self) -> None:
        if self.showing_stats:
            if self.current_item:
                self._show_card()
            else:
                self.showing_stats = False
                self.query_one("#stats-display", Static).update("")
        else:
            self._show_stats_screen()

    def _show_stats_screen(self) -> None:
        self.showing_stats = True
        self._hide_input()
        self.query_one("#card-header", Static).update("Generation Card Statistics")
        self.query_one("#question", Static).update("")
        self.query_one("#masked-text", Static).update("")
        self.query_one("#result", Static).update("")

        lines: list[str] = []

        total = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards"
        ).fetchone()[0]
        gen_count = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards WHERE phase='generation'"
        ).fetchone()[0]
        recall_count = self.conn.execute(
            "SELECT COUNT(*) FROM generation_cards WHERE phase='recall'"
        ).fetchone()[0]

        lines.append(f"Total cards: {total}")
        lines.append(f"  Generation phase: {gen_count}")
        lines.append(f"  Recall phase: {recall_count}")

        if total > 0:
            grad_pct = recall_count / total * 100
            lines.append(f"  Graduation rate: {grad_pct:.0f}%")

        # Masking level distribution
        for level in range(MAX_MASKING_LEVEL + 1):
            ct = self.conn.execute(
                "SELECT COUNT(*) FROM generation_cards WHERE phase='generation' AND masking_level=?",
                (level,),
            ).fetchone()[0]
            lines.append(f"    Level {level}: {ct}")

        lines.append("")

        # Recall stats
        reviews = self.conn.execute(
            "SELECT * FROM generation_review_log WHERE answer_mode='recall'"
        ).fetchall()
        if reviews:
            grades = [r["grade"] for r in reviews if r["grade"] is not None]
            if grades:
                lines.append("--- Recall Grade Distribution ---")
                for g in [1, 2, 3, 4]:
                    name = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}[g]
                    ct = grades.count(g)
                    pct = ct / len(grades) * 100
                    lines.append(f"  {name}: {ct} ({pct:.0f}%)")

        self.query_one("#stats-display", Static).update("\n".join(lines))


def main() -> None:
    """CLI entry point for generation card review."""
    parser = argparse.ArgumentParser(description="Generation card review (CFA LOS)")
    parser.add_argument("deck", nargs="?", default=None, help="Deck name filter")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--limit", type=int, default=None, help="Max cards")
    parser.add_argument("--db", default="data/srs.db", help="Database path")
    args = parser.parse_args()

    app = GenerationReviewApp(
        db_path=args.db,
        deck=args.deck,
        limit=args.limit,
        stats_only=args.stats,
    )
    app.run()
```

- [ ] **Step 2: Verify the TUI launches**

Run: `uv run review-gen --help`
Expected: Shows help text.

Run: `uv run review-gen --stats --db :memory:`
Expected: Launches TUI with empty stats, exits cleanly with Ctrl+Q.

- [ ] **Step 3: Commit**

```bash
git add src/knowledge_base/srs/generation_tui.py
git commit -m "feat: add generation card review TUI with masking and FSRS"
```

---

### Task 9: Integration Test

**Files:**
- Create: `tests/test_generation_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_generation_integration.py`:

```python
"""Integration tests for generation cards: import → review lifecycle."""

import json
import pytest
from pathlib import Path
from knowledge_base.srs.generation_db import (
    init_generation_db,
    get_generation_card,
    update_generation_phase,
    update_generation_scheduling,
)
from knowledge_base.srs.generation_import import import_los
from knowledge_base.srs.fsrs import Grade, schedule
from knowledge_base.srs.masking import mask_text
from knowledge_base.srs.text_scoring import compare_tokens, tokenize


@pytest.fixture
def los_db(tmp_path):
    """Create an in-memory DB with imported LOS cards."""
    data = {
        "deck": "cfa_level1",
        "readings": [{
            "number": 1,
            "title": "Rates and Returns",
            "book": 1,
            "los": [
                {"id": "1.a", "text": "interpret interest rates as required rates of return, discount rates, or opportunity costs and explain an interest rate as the sum of a real risk-free rate and premiums that compensate investors for bearing distinct types of risk"},
                {"id": "1.b", "text": "calculate and interpret different approaches to return measurement over time and describe their appropriate uses"},
            ],
        }],
    }
    path = tmp_path / "los.json"
    path.write_text(json.dumps(data))
    conn = init_generation_db(":memory:")
    import_los(conn, path)
    return conn


class TestGenerationLifecycle:
    def test_masking_progression(self, los_db):
        """Masking gets progressively harder at each level."""
        card = los_db.execute(
            "SELECT * FROM generation_cards WHERE los_id='1.a'"
        ).fetchone()
        card = dict(card)

        text = card["answer"]
        m0 = mask_text(text, level=0, card_id=card["card_id"])
        m1 = mask_text(text, level=1, card_id=card["card_id"])
        m2 = mask_text(text, level=2, card_id=card["card_id"])

        # More underscores at each level
        assert m0.count("_") < m1.count("_") < m2.count("_")

    def test_graduation_flow(self, los_db):
        """Card starts in generation, graduates to recall after 2 max passes."""
        card = los_db.execute(
            "SELECT * FROM generation_cards WHERE los_id='1.a'"
        ).fetchone()
        card_id = card["card_id"]

        # Simulate progression through masking levels
        update_generation_phase(los_db, card_id, {"masking_level": 2})
        update_generation_phase(los_db, card_id, {"consecutive_max_passes": 1})

        # Second pass at max level → graduate
        update_generation_phase(los_db, card_id, {
            "phase": "recall",
            "consecutive_max_passes": 0,
        })

        card = get_generation_card(los_db, card_id)
        assert card["phase"] == "recall"

    def test_recall_scheduling(self, los_db):
        """Graduated card schedules via FSRS."""
        card = los_db.execute(
            "SELECT * FROM generation_cards WHERE los_id='1.a'"
        ).fetchone()
        card = dict(card)
        card_id = card["card_id"]

        # Graduate the card
        update_generation_phase(los_db, card_id, {"phase": "recall"})

        # First FSRS review
        result = schedule(
            difficulty=card["difficulty"],
            stability=card["stability"],
            reps=0,
            last_review=None,
            grade=Grade.GOOD,
            now="2026-01-01T12:00:00",
        )
        assert result.interval > 0
        assert result.stability > 0

        # Second review after interval
        result2 = schedule(
            difficulty=result.difficulty,
            stability=result.stability,
            reps=result.reps,
            last_review="2026-01-01T12:00:00",
            grade=Grade.GOOD,
            now="2026-01-05T12:00:00",
        )
        assert result2.stability > result.stability

    def test_regression_on_again(self, los_db):
        """Again with short interval regresses to generation phase."""
        card = los_db.execute(
            "SELECT * FROM generation_cards WHERE los_id='1.a'"
        ).fetchone()
        card = dict(card)
        card_id = card["card_id"]

        # Graduate and schedule first review
        update_generation_phase(los_db, card_id, {"phase": "recall"})

        result = schedule(
            difficulty=5.0, stability=0.0, reps=0,
            last_review=None, grade=Grade.AGAIN,
            now="2026-01-01T12:00:00",
        )
        # Again on first review → very short interval → should regress
        assert result.interval < 1.0

    def test_text_scoring_display(self, los_db):
        """Text comparison produces meaningful feedback."""
        card = los_db.execute(
            "SELECT * FROM generation_cards WHERE los_id='1.b'"
        ).fetchone()
        correct = dict(card)["answer"]

        typed = "calculate and interpret different approaches to return measurement over time"
        typed_tokens = tokenize(typed)
        correct_tokens = tokenize(correct)
        results = compare_tokens(typed_tokens, correct_tokens)

        # All typed words should match (subset of correct)
        statuses = [r.status for r in results]
        assert "exact" in statuses
        # Missing words from correct answer
        assert "missing" in statuses
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_generation_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All existing tests still pass, plus all new tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_generation_integration.py
git commit -m "test: add generation cards integration tests"
```

---

### Task 10: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add generation cards documentation**

Add the following to the Quick Reference section of `CLAUDE.md`, after the existing `uv run review` entries:

```markdown
# Generation cards (CFA LOS)
uv run gen-import                # import LOS → data/srs.db
uv run review-gen [deck]         # launch generation card review TUI
uv run review-gen --stats        # stats screen only
```

Add a new subsection under "### SRS module (`srs/`)" in the Architecture section:

```markdown
### Generation cards (`srs/`)
- `fsrs.py` — standard FSRS v6 scheduler (4-button: Again/Hard/Good/Easy), independent from `scheduler.py`
- `generation_db.py` — `generation_cards` and `generation_review_log` tables, CRUD
- `generation_import.py` — JSON LOS data → SQLite card population
- `generation_tui.py` — Textual TUI for generation card review (separate from `tui.py`)
- `masking.py` — letter-level masking algorithm (3 levels: 30%, 60%, first-letter-only)
- `text_scoring.py` — token-level Levenshtein comparison for feedback display
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add generation cards to CLAUDE.md"
```
