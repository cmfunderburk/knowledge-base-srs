"""Tests for srs/text_scoring.py — token-level Levenshtein text comparison."""

import pytest
from knowledge_base.srs.text_scoring import (
    levenshtein,
    tokenize,
    TokenResult,
    compare_tokens,
)


# ---------------------------------------------------------------------------
# TestLevenshtein
# ---------------------------------------------------------------------------

class TestLevenshtein:
    def test_identical_strings(self):
        """Identical strings → distance 0."""
        assert levenshtein("hello", "hello") == 0

    def test_one_substitution(self):
        """One character substitution → distance 1."""
        assert levenshtein("cat", "bat") == 1

    def test_one_insertion(self):
        """One character insertion → distance 1."""
        assert levenshtein("cat", "cats") == 1

    def test_one_deletion(self):
        """One character deletion → distance 1."""
        assert levenshtein("cats", "cat") == 1

    def test_completely_different(self):
        """'abc' vs 'xyz' → distance 3."""
        assert levenshtein("abc", "xyz") == 3

    def test_both_empty(self):
        """Two empty strings → distance 0."""
        assert levenshtein("", "") == 0

    def test_one_empty(self):
        """One empty string → distance equals length of the other."""
        assert levenshtein("", "hello") == 5
        assert levenshtein("hello", "") == 5


# ---------------------------------------------------------------------------
# TestTokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_basic_splitting(self):
        """Space-separated words are split into tokens."""
        assert tokenize("hello world") == ["hello", "world"]

    def test_strips_punctuation_commas(self):
        """Commas attached to words are stripped."""
        assert tokenize("hello, world") == ["hello", "world"]

    def test_strips_punctuation_periods(self):
        """Trailing periods are stripped."""
        assert tokenize("end.") == ["end"]

    def test_strips_various_punctuation(self):
        """Semicolons, colons, exclamation marks, question marks stripped."""
        assert tokenize("wait; stop! really?") == ["wait", "stop", "really"]

    def test_lowercases(self):
        """All tokens are lowercased."""
        assert tokenize("Hello World") == ["hello", "world"]

    def test_empty_string(self):
        """Empty string → empty list."""
        assert tokenize("") == []

    def test_mixed_case_punctuation(self):
        """Mixed case with punctuation is lowercased and stripped."""
        assert tokenize("GDP, GNI.") == ["gdp", "gni"]


# ---------------------------------------------------------------------------
# TestCompareTokens
# ---------------------------------------------------------------------------

class TestCompareTokens:
    def test_exact_match_all_exact(self):
        """All tokens match exactly → all 'exact'."""
        results = compare_tokens(["the", "cat", "sat"], ["the", "cat", "sat"])
        assert all(r.status == "exact" for r in results)
        assert len(results) == 3

    def test_exact_match_fields(self):
        """TokenResult has expected, typed, status fields."""
        results = compare_tokens(["hello"], ["hello"])
        r = results[0]
        assert r.expected == "hello"
        assert r.typed == "hello"
        assert r.status == "exact"

    def test_typo_accepted_as_close(self):
        """Levenshtein distance of 1 → 'close'."""
        # 'helo' vs 'hello' → 1 deletion
        results = compare_tokens(["helo"], ["hello"])
        assert results[0].status == "close"

    def test_close_token_fields(self):
        """Close match has correct expected and typed fields."""
        results = compare_tokens(["helo"], ["hello"])
        r = results[0]
        assert r.expected == "hello"
        assert r.typed == "helo"
        assert r.status == "close"

    def test_wrong_word(self):
        """Token with Levenshtein > 1 → 'wrong'."""
        results = compare_tokens(["dog"], ["cat"])
        assert results[0].status == "wrong"

    def test_wrong_token_fields(self):
        """Wrong token has correct expected and typed fields."""
        results = compare_tokens(["xyz"], ["abc"])
        r = results[0]
        assert r.expected == "abc"
        assert r.typed == "xyz"
        assert r.status == "wrong"

    def test_extra_typed_words(self):
        """Extra typed words beyond correct length → 'extra'."""
        results = compare_tokens(["hello", "world", "extra"], ["hello", "world"])
        assert results[0].status == "exact"
        assert results[1].status == "exact"
        assert results[2].status == "extra"
        assert results[2].typed == "extra"
        assert results[2].expected == ""

    def test_missing_words(self):
        """Missing words (typed shorter than correct) → 'missing'."""
        results = compare_tokens(["hello"], ["hello", "world"])
        assert results[0].status == "exact"
        assert results[1].status == "missing"
        assert results[1].expected == "world"
        assert results[1].typed == ""

    def test_empty_typed_all_missing(self):
        """Empty typed → all correct words are 'missing'."""
        results = compare_tokens([], ["one", "two"])
        assert len(results) == 2
        assert all(r.status == "missing" for r in results)

    def test_empty_correct_all_extra(self):
        """Empty correct → all typed words are 'extra'."""
        results = compare_tokens(["one", "two"], [])
        assert len(results) == 2
        assert all(r.status == "extra" for r in results)

    def test_both_empty(self):
        """Both empty → empty result list."""
        results = compare_tokens([], [])
        assert results == []

    def test_mixed_statuses(self):
        """Mixed scenario: exact, close, wrong, missing."""
        typed = ["the", "kat", "runned"]
        correct = ["the", "cat", "ran", "fast"]
        results = compare_tokens(typed, correct)
        assert results[0].status == "exact"   # "the" == "the"
        assert results[1].status == "close"   # "kat" vs "cat" → dist 1
        assert results[2].status == "wrong"   # "runned" vs "ran" → dist 3
        assert results[3].status == "missing"  # "fast" missing
