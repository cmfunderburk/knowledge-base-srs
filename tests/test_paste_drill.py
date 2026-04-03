"""Tests for paste-and-drill mode: split_paste_text and GenerationReviewApp paste_cards."""

from __future__ import annotations

from knowledge_base.srs.generation_tui import split_paste_text


class TestSplitPasteText:
    def test_split_by_sentence(self):
        text = "First sentence. Second sentence. Third sentence."
        cards = split_paste_text(text, split_by="sentence")
        assert len(cards) == 3

    def test_split_by_line(self):
        text = "Line one\nLine two\nLine three"
        cards = split_paste_text(text, split_by="line")
        assert len(cards) == 3

    def test_empty_lines_skipped(self):
        text = "Line one\n\n\nLine two"
        cards = split_paste_text(text, split_by="line")
        assert len(cards) == 2

    def test_empty_input(self):
        assert split_paste_text("", split_by="sentence") == []
        assert split_paste_text("", split_by="line") == []

    def test_whitespace_only(self):
        assert split_paste_text("   \n  \n  ", split_by="line") == []
