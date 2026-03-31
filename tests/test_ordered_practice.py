"""Tests for ordered practice mode in generation_tui."""

from __future__ import annotations

import json

import pytest

from collections import deque

from knowledge_base.srs.generation_db import init_generation_db
from knowledge_base.srs.generation_import import import_los
from knowledge_base.srs.generation_tui import (
    GenerationReviewApp,
    QueueItem,
    MAX_MASKING_LEVEL,
    PRACTICE_TYPEIN_LEVEL,
    _los_sort_key,
)


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


@pytest.fixture
def ordered_app(tmp_path):
    """Create an app in ordered practice mode with 5 cards across 2 readings."""
    data = {
        "deck": "cfa_level1",
        "readings": [
            {
                "number": 1,
                "title": "Rates and Returns",
                "book": 1,
                "los": [
                    {"id": "1.a", "text": "interpret interest rates"},
                    {"id": "1.b", "text": "explain discount rates"},
                    {"id": "1.c", "text": "calculate holding period return"},
                ],
            },
            {
                "number": 2,
                "title": "Time Value of Money",
                "book": 1,
                "los": [
                    {"id": "2.a", "text": "calculate future value"},
                    {"id": "2.b", "text": "calculate present value"},
                ],
            },
        ],
    }
    json_path = tmp_path / "los.json"
    json_path.write_text(json.dumps(data))
    db_path = tmp_path / "test.db"

    conn = init_generation_db(db_path=str(db_path))
    import_los(conn, data_path=json_path)
    conn.close()

    app = GenerationReviewApp(
        db_path=str(db_path),
        ordered_practice="1-2",
    )
    return app


class TestOrderedPracticeQueue:
    def test_queue_is_in_los_order(self, ordered_app):
        """Ordered practice queue should be sorted by natural LOS order."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        los_ids = [item.card["los_id"] for item in ordered_app.queue]
        assert los_ids == ["1.a", "1.b", "1.c", "2.a", "2.b"]

    def test_all_delays_are_zero(self, ordered_app):
        """All items in ordered queue should have delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        for item in ordered_app.queue:
            assert item.delay == 0

    def test_all_cards_start_at_level_0(self, ordered_app):
        """All cards in ordered practice start at generation level 0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        for item in ordered_app.queue:
            assert item.card["phase"] == "generation"
            assert item.card["masking_level"] == 0


class TestOrderedPracticeRequeue:
    def test_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """In ordered mode, pass should always requeue with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        # Pop the first item (1.a) and simulate a pass at level 0
        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = 0

        ordered_app._show_next = lambda: None
        ordered_app._handle_practice_pass(item, card, level=0)

        # Card should be at the back of the queue
        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0
        assert last_item.card["masking_level"] == 1

    def test_fail_requeues_at_end_with_zero_delay(self, ordered_app):
        """In ordered mode, fail should always requeue with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        # Pop the first item and simulate a fail at level 1
        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = 1

        ordered_app._show_next = lambda: None
        ordered_app._handle_generation_fail()

        # Card should be at the back with delay=0
        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0
        assert last_item.card["masking_level"] == 0

    def test_order_preserved_after_multiple_reviews(self, ordered_app):
        """After popping and re-queuing several cards, order is preserved."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        original_order = [item.card["los_id"] for item in ordered_app.queue]

        # Simulate reviewing all 5 cards: pop front, push to back
        for _ in range(5):
            item = ordered_app.queue.popleft()
            ordered_app.queue.append(QueueItem(card=item.card, delay=0))

        after_cycle = [item.card["los_id"] for item in ordered_app.queue]
        assert after_cycle == original_order

    def test_typein_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """Type-in level pass in ordered mode also re-queues with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = PRACTICE_TYPEIN_LEVEL

        ordered_app._show_next = lambda: None
        ordered_app._handle_practice_pass(item, card, level=PRACTICE_TYPEIN_LEVEL)

        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0

    def test_max_masking_pass_requeues_at_end_with_zero_delay(self, ordered_app):
        """Pass at max masking in ordered mode re-queues with delay=0."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()

        item = ordered_app.queue.popleft()
        ordered_app._current_item = item
        card = item.card
        card["masking_level"] = MAX_MASKING_LEVEL
        card["_practice_max_passes"] = 0

        ordered_app._show_next = lambda: None
        ordered_app._handle_practice_pass(item, card, level=MAX_MASKING_LEVEL)

        last_item = ordered_app.queue[-1]
        assert last_item.card["los_id"] == "1.a"
        assert last_item.delay == 0


class TestOrderedPracticeHeader:
    def test_app_title_is_ordered_practice(self, ordered_app):
        """App title should be 'Ordered Practice' in ordered mode."""
        ordered_app.conn = init_generation_db(db_path=ordered_app.db_path)
        ordered_app._build_ordered_practice_queue()
        assert ordered_app.ordered_practice is True
        assert ordered_app.practice_mode is True

    def test_regular_practice_flag_not_ordered(self, tmp_path):
        """Regular --practice should not set ordered_practice."""
        data = {
            "deck": "cfa_level1",
            "readings": [{
                "number": 1, "title": "Test", "book": 1,
                "los": [{"id": "1.a", "text": "test text"}],
            }],
        }
        json_path = tmp_path / "los.json"
        json_path.write_text(json.dumps(data))
        db_path = tmp_path / "test.db"
        conn = init_generation_db(db_path=str(db_path))
        import_los(conn, data_path=json_path)
        conn.close()

        app = GenerationReviewApp(
            db_path=str(db_path),
            practice="1",
        )
        assert app.practice_mode is True
        assert app.ordered_practice is False
