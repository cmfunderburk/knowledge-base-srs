"""Tests for ordered practice mode in generation_tui."""

from __future__ import annotations

import pytest

from knowledge_base.srs.generation_tui import _los_sort_key


class TestLosSortKey:
    def test_single_digit_reading(self):
        assert _los_sort_key({"los_id": "1.a"}) == (1, "a")

    def test_double_digit_reading(self):
        assert _los_sort_key({"los_id": "10.b"}) == (10, "b")

    def test_natural_order_across_readings(self):
        """Sorting by key puts 2.a before 10.a (not lexicographic '10' < '2')."""
        cards = [
            {"los_id": "10.a"},
            {"los_id": "2.a"},
            {"los_id": "1.c"},
            {"los_id": "1.a"},
            {"los_id": "1.b"},
        ]
        sorted_ids = [c["los_id"] for c in sorted(cards, key=_los_sort_key)]
        assert sorted_ids == ["1.a", "1.b", "1.c", "2.a", "10.a"]

    def test_within_reading_alphabetical(self):
        cards = [
            {"los_id": "5.c"},
            {"los_id": "5.a"},
            {"los_id": "5.b"},
        ]
        sorted_ids = [c["los_id"] for c in sorted(cards, key=_los_sort_key)]
        assert sorted_ids == ["5.a", "5.b", "5.c"]
