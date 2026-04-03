"""Tests for srs/text_scoring.py — token-level Levenshtein text comparison."""

import pytest
from knowledge_base.srs.text_scoring import (
    levenshtein,
    tokenize,
    TokenResult,
    compare_tokens,
    check_exact_answer,
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


# ---------------------------------------------------------------------------
# TestCheckExactAnswer
# ---------------------------------------------------------------------------

class TestCheckExactAnswer:
    def test_exact_string_match(self):
        assert check_exact_answer("hello", "hello") is True

    def test_case_insensitive_string(self):
        assert check_exact_answer("Yes", "yes") is True

    def test_string_mismatch(self):
        assert check_exact_answer("hello", "world") is False

    def test_numeric_match_integers(self):
        assert check_exact_answer("1234", "1234") is True

    def test_numeric_match_with_commas(self):
        assert check_exact_answer("1234", "1,234") is True

    def test_numeric_match_trailing_zeros(self):
        assert check_exact_answer("6.20", "6.2") is True

    def test_numeric_match_float(self):
        assert check_exact_answer("3.14", "3.14") is True

    def test_numeric_mismatch(self):
        assert check_exact_answer("6.3", "6.2") is False

    def test_whitespace_stripped(self):
        assert check_exact_answer("  6.2  ", "6.2") is True

    def test_dollar_sign_stripped(self):
        assert check_exact_answer("$6.2", "6.2") is True

    def test_both_non_numeric_case_insensitive(self):
        assert check_exact_answer("YES", "yes") is True

    def test_empty_strings_match(self):
        assert check_exact_answer("", "") is True

    def test_comma_in_typed_and_stored(self):
        assert check_exact_answer("1,234", "1,234") is True

    def test_integer_vs_float_representation(self):
        assert check_exact_answer("100", "100.0") is True

    def test_en_dash_matches_hyphen(self):
        assert check_exact_answer("~$50,000-80,000", "~$50,000\u201380,000") is True

    def test_em_dash_matches_hyphen(self):
        assert check_exact_answer("50-60", "50\u201460") is True

    def test_extra_whitespace_normalized(self):
        assert check_exact_answer("50 - 60  years", "50 - 60 years") is True

    def test_tilde_optional(self):
        assert check_exact_answer("50000", "~$50,000") is True

    def test_dollar_sign_optional(self):
        assert check_exact_answer("50000-80000", "$50,000–80,000") is True

    def test_percent_suffix_optional(self):
        assert check_exact_answer("5-10", "5–10%") is True

    def test_unit_suffix_years_optional(self):
        assert check_exact_answer("73", "~73 years") is True

    def test_unit_suffix_tonnes_optional(self):
        assert check_exact_answer("5", "~5 tonnes") is True

    def test_both_typed_with_decorators(self):
        assert check_exact_answer("~$50,000", "~$50,000") is True

    def test_range_with_all_decorators(self):
        assert check_exact_answer("50000-80000", "~$50,000–80,000") is True

    def test_less_than_prefix(self):
        assert check_exact_answer("<1", "<1%") is True

    def test_greater_than_prefix(self):
        assert check_exact_answer(">100", ">100%") is True

    def test_negative_range(self):
        assert check_exact_answer("-2 to -5", "-2 to -5%") is True
