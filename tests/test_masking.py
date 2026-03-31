"""Tests for letter-level masking algorithm (test_masking.py)."""
import pytest
from knowledge_base.srs.masking import is_maskable, mask_word, mask_text


class TestIsMaskable:
    """Tests for is_maskable()."""

    def test_function_words_not_maskable(self):
        for word in ["the", "and", "for", "are", "that", "with", "from"]:
            assert is_maskable(word) is False, f"Expected '{word}' to be not maskable"

    def test_short_words_not_maskable(self):
        # Short words ≤3 chars
        for word in ["is", "of", "an", "tax", "GDP"]:
            assert is_maskable(word) is False, f"Expected '{word}' to be not maskable"

    def test_content_words_maskable(self):
        for word in ["interpret", "interest", "rates", "required", "premiums"]:
            assert is_maskable(word) is True, f"Expected '{word}' to be maskable"

    def test_numbers_not_maskable(self):
        for token in ["95%", "1-year", "2024", "10%"]:
            assert is_maskable(token) is False, f"Expected '{token}' to be not maskable"

    def test_acronyms_not_maskable(self):
        # All uppercase ≥2 chars
        for acronym in ["CAPM", "NPV", "FSRS", "SML", "WACC", "PV", "IRR"]:
            assert is_maskable(acronym) is False, f"Expected '{acronym}' to be not maskable"


class TestMaskWord:
    """Tests for mask_word()."""

    def test_first_letter_preserved_level0(self):
        word = "interpretation"
        result = mask_word(word, level=0, seed=42)
        assert result[0] == word[0]

    def test_first_letter_preserved_level1(self):
        word = "interpretation"
        result = mask_word(word, level=1, seed=42)
        assert result[0] == word[0]

    def test_first_letter_preserved_level2(self):
        word = "interpretation"
        result = mask_word(word, level=2, seed=42)
        assert result[0] == word[0]

    def test_level2_first_letter_only(self):
        word = "interpret"
        result = mask_word(word, level=2, seed=42)
        assert result[0] == "i"
        assert result[1:] == "_" * (len(word) - 1)
        assert result == "i________"

    def test_level2_all_others_masked(self):
        word = "premiums"
        result = mask_word(word, level=2, seed=0)
        assert result == "p" + "_" * (len(word) - 1)

    def test_level0_masks_approximately_30_percent(self):
        # "interpretation" has 14 chars; non-first = 13 chars
        # ~30% of 13 = ~3-4 masked
        word = "interpretation"
        result = mask_word(word, level=0, seed=7)
        non_first = result[1:]
        masked_count = non_first.count("_")
        # Allow a reasonable range around 30%: 1–6 masked out of 13
        assert 1 <= masked_count <= 6, f"Expected ~30% masked, got {masked_count}/13 masked"

    def test_level1_masks_approximately_60_percent(self):
        # "interpretation" has 14 chars; non-first = 13 chars
        # ~60% of 13 = ~7-8 masked
        word = "interpretation"
        result = mask_word(word, level=1, seed=7)
        non_first = result[1:]
        masked_count = non_first.count("_")
        # Allow a reasonable range around 60%: 5–10 masked out of 13
        assert 5 <= masked_count <= 10, f"Expected ~60% masked, got {masked_count}/13 masked"

    def test_deterministic_with_same_seed(self):
        word = "required"
        r1 = mask_word(word, level=0, seed=99)
        r2 = mask_word(word, level=0, seed=99)
        assert r1 == r2

    def test_different_seeds_different_patterns(self):
        # For a sufficiently long word, different seeds should usually produce different patterns
        word = "interpretation"
        results = set()
        for seed in range(20):
            results.add(mask_word(word, level=0, seed=seed))
        # With 20 different seeds, we should see at least a few distinct patterns
        assert len(results) > 5

    def test_no_consecutive_underscores_level0(self):
        word = "interpretation"
        for seed in range(20):
            result = mask_word(word, level=0, seed=seed)
            assert "__" not in result, f"Consecutive underscores found in '{result}' (seed={seed})"

    def test_no_consecutive_underscores_level1(self):
        word = "interpretation"
        for seed in range(20):
            result = mask_word(word, level=1, seed=seed)
            assert "__" not in result, f"Consecutive underscores found in '{result}' (seed={seed})"

    def test_short_words_returned_unchanged(self):
        for word in ["is", "of", "an", "tax", "GDP", "the"]:
            assert mask_word(word, level=0, seed=0) == word
            assert mask_word(word, level=1, seed=0) == word
            assert mask_word(word, level=2, seed=0) == word

    def test_result_same_length_as_input(self):
        word = "interest"
        for level in [0, 1, 2]:
            result = mask_word(word, level=level, seed=42)
            assert len(result) == len(word)


class TestMaskText:
    """Tests for mask_text()."""

    def test_function_words_preserved(self):
        text = "the required rate of return"
        result = mask_text(text, level=2, card_id="test_card")
        words = result.split()
        # "the", "of" are function words — must be preserved
        assert "the" in words
        assert "of" in words

    def test_deterministic_with_card_id(self):
        text = "the required rate of return for an investment"
        r1 = mask_text(text, level=1, card_id="card_001")
        r2 = mask_text(text, level=1, card_id="card_001")
        assert r1 == r2

    def test_different_card_ids_different_masks(self):
        text = "interpretation of interest rates and required premiums"
        r1 = mask_text(text, level=0, card_id="card_001")
        r2 = mask_text(text, level=0, card_id="card_002")
        # Different card_ids should produce different masking
        assert r1 != r2

    def test_level2_first_letter_only_for_content_words(self):
        text = "interpretation of interest rates"
        result = mask_text(text, level=2, card_id="abc")
        words_in = text.split()
        words_out = result.split()
        assert len(words_in) == len(words_out)
        # "interpretation" → "i_____________"
        interp_out = words_out[0]
        assert interp_out[0] == "i"
        assert set(interp_out[1:]) == {"_"}

    def test_punctuation_preserved(self):
        text = "rates, premiums, and returns"
        result = mask_text(text, level=2, card_id="x")
        # commas should still be present
        assert "," in result

    def test_empty_string(self):
        assert mask_text("", level=0, card_id="x") == ""

    def test_numbers_preserved(self):
        text = "a 95% confidence interval for 2024"
        result = mask_text(text, level=2, card_id="x")
        assert "95%" in result
        assert "2024" in result

    def test_acronyms_preserved(self):
        text = "the CAPM model requires NPV"
        result = mask_text(text, level=2, card_id="x")
        assert "CAPM" in result
        assert "NPV" in result
