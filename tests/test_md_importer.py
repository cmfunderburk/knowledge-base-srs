"""Tests for srs/md_importer.py — Markdown import parser."""
import json

import pytest

from knowledge_base.srs.generation_db import init_generation_db, get_cards_by_source
from knowledge_base.srs.md_importer import import_markdown, parse_markdown


# ---------------------------------------------------------------------------
# Section-keyed format
# ---------------------------------------------------------------------------


class TestSectionKeyedDashHeadings:
    """Dash-prefixed section headings: '- 1.2: Title'."""

    SAMPLE = """\
**Learning Module Overview**
- 1.2: Interest Rates and Time Value of Money
\t- An interest rate, *r*, can have three interpretations.
\t- An interest rate can be viewed as the sum of a real risk-free interest rate.
- 1.3: Rates of Return
\t- A financial asset's total return consists of two components.
"""

    def test_returns_list(self):
        result = parse_markdown(self.SAMPLE)
        assert isinstance(result, list)

    def test_section_count(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 2

    def test_section_ids(self):
        result = parse_markdown(self.SAMPLE)
        assert result[0]["section_id"] == "1.2"
        assert result[1]["section_id"] == "1.3"

    def test_section_titles(self):
        result = parse_markdown(self.SAMPLE)
        assert result[0]["section_title"] == "Interest Rates and Time Value of Money"
        assert result[1]["section_title"] == "Rates of Return"

    def test_card_count_per_section(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result[0]["cards"]) == 2
        assert len(result[1]["cards"]) == 1

    def test_card_text_content(self):
        result = parse_markdown(self.SAMPLE)
        assert "interpretations" in result[0]["cards"][0]
        assert "real risk-free" in result[0]["cards"][1]

    def test_preamble_skipped(self):
        """Content before first section heading is skipped."""
        result = parse_markdown(self.SAMPLE)
        # Section IDs start at 1.2, not preamble text
        ids = [s["section_id"] for s in result]
        assert "Learning Module Overview" not in ids


class TestSectionKeyedHashHeadings:
    """Hash-prefixed section headings: '## 1.2: Title' or '### 1.2 Title'."""

    SAMPLE_COLON = """\
## 1.2: Interest Rates
\t- First card about rates.
\t- Second card about rates.
## 1.3: Time Value
\t- Card about time value.
"""

    SAMPLE_SPACE = """\
### 1.2 Interest Rates
\t- First card about rates.
### 1.3 Time Value
\t- Card about time value.
"""

    def test_hash_colon_section_ids(self):
        result = parse_markdown(self.SAMPLE_COLON)
        assert result[0]["section_id"] == "1.2"
        assert result[1]["section_id"] == "1.3"

    def test_hash_colon_section_titles(self):
        result = parse_markdown(self.SAMPLE_COLON)
        assert result[0]["section_title"] == "Interest Rates"
        assert result[1]["section_title"] == "Time Value"

    def test_hash_space_section_ids(self):
        result = parse_markdown(self.SAMPLE_SPACE)
        assert result[0]["section_id"] == "1.2"
        assert result[1]["section_id"] == "1.3"

    def test_hash_space_section_titles(self):
        result = parse_markdown(self.SAMPLE_SPACE)
        assert result[0]["section_title"] == "Interest Rates"
        assert result[1]["section_title"] == "Time Value"

    def test_hash_cards(self):
        result = parse_markdown(self.SAMPLE_COLON)
        assert len(result[0]["cards"]) == 2
        assert len(result[1]["cards"]) == 1


class TestSectionKeyedSubBulletFolding:
    """Sub-bullets (double tab indent) fold into their parent bullet."""

    SAMPLE = """\
- 1.2: Concepts
\t- Main point about X.
\t\t- Sub-detail one.
\t\t- Sub-detail two.
\t- Another main point.
"""

    def test_sub_bullets_folded_into_parent(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 1
        cards = result[0]["cards"]
        # Sub-bullets fold into the first card
        assert len(cards) == 2
        assert "Main point about X" in cards[0]
        assert "Sub-detail one" in cards[0]
        assert "Sub-detail two" in cards[0]

    def test_second_card_separate(self):
        result = parse_markdown(self.SAMPLE)
        assert "Another main point" in result[0]["cards"][1]


class TestSectionKeyedEmptySections:
    """Empty sections (heading with no cards) are skipped."""

    SAMPLE = """\
- 1.2: Empty Section
- 1.3: Non-empty Section
\t- A real card here.
"""

    def test_empty_section_skipped(self):
        result = parse_markdown(self.SAMPLE)
        ids = [s["section_id"] for s in result]
        assert "1.2" not in ids

    def test_non_empty_section_present(self):
        result = parse_markdown(self.SAMPLE)
        ids = [s["section_id"] for s in result]
        assert "1.3" in ids


class TestSectionKeyedPreambleSkipping:
    """Multiple preamble lines before first heading are all skipped."""

    SAMPLE = """\
# Module Title

Some introduction text here.
More preamble.

- 1.1: First Section
\t- Card one.
"""

    def test_preamble_completely_skipped(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 1
        assert result[0]["section_id"] == "1.1"


# ---------------------------------------------------------------------------
# LOS-keyed format
# ---------------------------------------------------------------------------


class TestLOSKeyedHeadings:
    """'### LOS 1.a' style headings."""

    SAMPLE = """\
### LOS 1.a
- An interest rate can be interpreted as the rate of return required in equilibrium.
- Securities may have several risks increasing the required rate of return.
### LOS 1.b
- Holding period return is used to measure an investment's return over a specific period.
"""

    def test_returns_two_sections(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 2

    def test_section_ids(self):
        result = parse_markdown(self.SAMPLE)
        assert result[0]["section_id"] == "1.a"
        assert result[1]["section_id"] == "1.b"

    def test_section_title_is_none(self):
        """LOS-keyed sections have no title."""
        result = parse_markdown(self.SAMPLE)
        assert result[0]["section_title"] is None
        assert result[1]["section_title"] is None

    def test_card_counts(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result[0]["cards"]) == 2
        assert len(result[1]["cards"]) == 1

    def test_card_text(self):
        result = parse_markdown(self.SAMPLE)
        assert "equilibrium" in result[0]["cards"][0]
        assert "Holding period" in result[1]["cards"][0]


class TestLOSKeyedConsecutiveLinesJoined:
    """Consecutive non-bullet lines under a LOS heading join into a single card."""

    SAMPLE = """\
### LOS 2.a
This is line one of a paragraph.
This is line two of the same paragraph.

This is a separate paragraph that forms a second card.
"""

    def test_consecutive_lines_single_card(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 1
        cards = result[0]["cards"]
        # Two paragraphs (separated by blank line) → two cards
        assert len(cards) == 2
        assert "line one" in cards[0]
        assert "line two" in cards[0]

    def test_separate_paragraph_is_separate_card(self):
        result = parse_markdown(self.SAMPLE)
        assert "separate paragraph" in result[0]["cards"][1]


class TestLOSKeyedEmptySection:
    """LOS sections with no content are skipped."""

    SAMPLE = """\
### LOS 1.a
### LOS 1.b
- A real card.
"""

    def test_empty_los_section_skipped(self):
        result = parse_markdown(self.SAMPLE)
        ids = [s["section_id"] for s in result]
        assert "1.a" not in ids
        assert "1.b" in ids


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestAutoDetection:
    """Auto-detect format from content."""

    SECTION_KEYED = """\
- 1.2: Interest Rates
\t- A card about interest rates.
"""

    LOS_KEYED = """\
### LOS 1.a
- A card about rates.
"""

    def test_auto_detects_section_keyed(self):
        result = parse_markdown(self.SECTION_KEYED)
        assert result[0]["section_id"] == "1.2"
        assert result[0]["section_title"] == "Interest Rates"

    def test_auto_detects_los_keyed(self):
        result = parse_markdown(self.LOS_KEYED)
        assert result[0]["section_id"] == "1.a"
        assert result[0]["section_title"] is None

    def test_forced_section_format(self):
        result = parse_markdown(self.SECTION_KEYED, format="section")
        assert result[0]["section_id"] == "1.2"

    def test_forced_los_format(self):
        result = parse_markdown(self.LOS_KEYED, format="los")
        assert result[0]["section_id"] == "1.a"

    def test_no_headings_raises_value_error(self):
        text = "Just some plain text with no headings.\nAnother line."
        with pytest.raises(ValueError):
            parse_markdown(text)

    def test_no_headings_forced_section_raises(self):
        text = "No headings here at all."
        with pytest.raises(ValueError):
            parse_markdown(text, format="section")

    def test_no_headings_forced_los_raises(self):
        text = "No headings here at all."
        with pytest.raises(ValueError):
            parse_markdown(text, format="los")


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


class TestResultShape:
    """Validate the structure of returned dicts."""

    SAMPLE = """\
- 1.2: Interest Rates
\t- A card.
"""

    def test_each_result_has_section_id(self):
        result = parse_markdown(self.SAMPLE)
        for section in result:
            assert "section_id" in section

    def test_each_result_has_section_title(self):
        result = parse_markdown(self.SAMPLE)
        for section in result:
            assert "section_title" in section

    def test_each_result_has_cards(self):
        result = parse_markdown(self.SAMPLE)
        for section in result:
            assert "cards" in section
            assert isinstance(section["cards"], list)

    def test_cards_are_strings(self):
        result = parse_markdown(self.SAMPLE)
        for section in result:
            for card in section["cards"]:
                assert isinstance(card, str)


# ---------------------------------------------------------------------------
# Real-world CFA sample data
# ---------------------------------------------------------------------------


class TestRealWorldSectionKeyed:
    """Test against the real-world CFA Official reading sample from the spec."""

    SAMPLE = """\
**Learning Module Overview**
- 1.2: Interest Rates and Time Value of Money
\t- An interest rate, *r*, can have three interpretations: (1) a required rate of return, (2) a discount rate, or (3) an opportunity cost.
\t- An interest rate can be viewed as the sum of a real risk-free interest rate and premiums.
\t- The nominal risk-free interest rate is approximated as the sum of the real risk-free rate and inflation.
- 1.3: Rates of Return
\t- A financial asset's total return consists of two components: income yield and capital gain/loss.
"""

    def test_two_sections_parsed(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 2

    def test_section_12_has_three_cards(self):
        result = parse_markdown(self.SAMPLE)
        section_12 = next(s for s in result if s["section_id"] == "1.2")
        assert len(section_12["cards"]) == 3

    def test_section_13_has_one_card(self):
        result = parse_markdown(self.SAMPLE)
        section_13 = next(s for s in result if s["section_id"] == "1.3")
        assert len(section_13["cards"]) == 1

    def test_section_12_title(self):
        result = parse_markdown(self.SAMPLE)
        section_12 = next(s for s in result if s["section_id"] == "1.2")
        assert section_12["section_title"] == "Interest Rates and Time Value of Money"

    def test_italic_markup_preserved(self):
        """Markdown inline markup is preserved in card text."""
        result = parse_markdown(self.SAMPLE)
        section_12 = next(s for s in result if s["section_id"] == "1.2")
        assert "*r*" in section_12["cards"][0]


class TestRealWorldLOSKeyed:
    """Test against the real-world Schweser sample from the spec."""

    SAMPLE = """\
### LOS 1.a
- An interest rate can be interpreted as the rate of return required in equilibrium.
- Securities may have several risks increasing the required rate of return.
### LOS 1.b
- Holding period return is used to measure an investment's return over a specific period.
"""

    def test_two_sections(self):
        result = parse_markdown(self.SAMPLE)
        assert len(result) == 2

    def test_los_1a_two_cards(self):
        result = parse_markdown(self.SAMPLE)
        los_1a = next(s for s in result if s["section_id"] == "1.a")
        assert len(los_1a["cards"]) == 2

    def test_los_1b_one_card(self):
        result = parse_markdown(self.SAMPLE)
        los_1b = next(s for s in result if s["section_id"] == "1.b")
        assert len(los_1b["cards"]) == 1


# ---------------------------------------------------------------------------
# import_markdown — DB integration
# ---------------------------------------------------------------------------


class TestImportMarkdown:
    """Tests for import_markdown() — parsing + DB upsert."""

    # Section-keyed sample: 2 sections, 3 + 1 = 4 cards total
    SECTION_SAMPLE = """\
- 1.2: Interest Rates and Time Value of Money
\t- An interest rate can have three interpretations.
\t- An interest rate can be viewed as the sum of a real risk-free interest rate.
\t- The nominal risk-free rate is approximated as the real rate plus inflation.
- 1.3: Rates of Return
\t- A financial asset's total return consists of income yield and capital gain/loss.
"""

    # LOS-keyed sample: 2 sections, 2 + 1 = 3 cards total
    LOS_SAMPLE = """\
### LOS 1.a
- An interest rate can be interpreted as the rate of return required in equilibrium.
- Securities may have several risks increasing the required rate of return.
### LOS 1.b
- Holding period return is used to measure an investment's return over a specific period.
"""

    def _make_conn(self):
        return init_generation_db(db_path=":memory:")

    # ------------------------------------------------------------------
    # Card count
    # ------------------------------------------------------------------

    def test_returns_correct_card_count_section(self):
        conn = self._make_conn()
        n = import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        assert n == 4

    def test_returns_correct_card_count_los(self):
        conn = self._make_conn()
        n = import_markdown(conn, self.LOS_SAMPLE, deck="test", topic_id="1", source="md")
        assert n == 3

    def test_cards_written_to_db(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        assert len(cards) == 4

    # ------------------------------------------------------------------
    # Field correctness
    # ------------------------------------------------------------------

    def test_section_id_set(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        section_ids = {c["section_id"] for c in cards}
        assert "1.2" in section_ids
        assert "1.3" in section_ids

    def test_section_title_set(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        card_12 = next(c for c in cards if c["section_id"] == "1.2" and c["card_index"] == 0)
        assert card_12["section_title"] == "Interest Rates and Time Value of Money"

    def test_section_title_none_for_los(self):
        conn = self._make_conn()
        import_markdown(conn, self.LOS_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        for card in cards:
            assert card["section_title"] is None

    def test_card_index_set(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        cards_12 = sorted(
            [c for c in cards if c["section_id"] == "1.2"],
            key=lambda c: c["card_index"],
        )
        assert [c["card_index"] for c in cards_12] == [0, 1, 2]

    def test_source_stored(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md_notes")
        cards = get_cards_by_source(conn, source="md_notes", deck="test")
        assert all(c["source"] == "md_notes" for c in cards)

    def test_topic_id_stored(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="42", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        assert all(c["topic_id"] == "42" for c in cards)

    def test_answer_is_card_text(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        card_13 = next(c for c in cards if c["section_id"] == "1.3")
        assert "income yield" in card_13["answer"]

    # ------------------------------------------------------------------
    # Question format
    # ------------------------------------------------------------------

    def test_question_with_section_title(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        card = next(c for c in cards if c["section_id"] == "1.2" and c["card_index"] == 0)
        assert card["question"] == "1.2: Interest Rates and Time Value of Money [1/3]"

    def test_question_without_section_title(self):
        conn = self._make_conn()
        import_markdown(conn, self.LOS_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        card = next(c for c in cards if c["section_id"] == "1.a" and c["card_index"] == 0)
        assert card["question"] == "LOS 1.a [1/2]"

    def test_question_last_card_in_section(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        card = next(c for c in cards if c["section_id"] == "1.2" and c["card_index"] == 2)
        assert card["question"] == "1.2: Interest Rates and Time Value of Money [3/3]"

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def test_tags_contain_reading_tag(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="5", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        for card in cards:
            tags = json.loads(card["tags"])
            assert "reading::5" in tags

    def test_tags_contain_source_tag(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="5", source="my_notes")
        cards = get_cards_by_source(conn, source="my_notes", deck="test")
        for card in cards:
            tags = json.loads(card["tags"])
            assert "source::my_notes" in tags

    def test_tags_is_json_array(self):
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        for card in cards:
            tags = json.loads(card["tags"])
            assert isinstance(tags, list)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_idempotent_import(self):
        """Importing the same markdown twice produces no duplicate cards."""
        conn = self._make_conn()
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        cards = get_cards_by_source(conn, source="md", deck="test")
        assert len(cards) == 4

    def test_idempotent_returns_same_count(self):
        """Second import returns same card count as first."""
        conn = self._make_conn()
        n1 = import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        n2 = import_markdown(conn, self.SECTION_SAMPLE, deck="test", topic_id="1", source="md")
        assert n1 == n2 == 4
