"""Tests for back-to-catalog (Ctrl+B) feature."""

from knowledge_base.srs.generation_tui import GenerationReviewApp, QueueItem


class TestResetSessionState:
    def test_reset_clears_queue_and_counters(self):
        app = GenerationReviewApp(db_path=":memory:")
        app.queue = [QueueItem(card={"card_id": 1})]
        app.total_reviewed = 5
        app.total_cards = 10
        app._pass_counts = {1: 3, 2: 1}

        app._reset_session_state()

        assert app.queue == []
        assert app.total_reviewed == 0
        assert app.total_cards == 0
        assert app._pass_counts == {}

    def test_reset_clears_state_machine_flags(self):
        app = GenerationReviewApp(db_path=":memory:")
        app._awaiting_gen_grade = True
        app._awaiting_recall_grade = True
        app._awaiting_advance = True
        app._pending_requeue = (QueueItem(card={"card_id": 1}), 3)
        app._current_item = QueueItem(card={"card_id": 1})
        app._last_diff_markup = "some markup"
        app.showing_stats = True

        app._reset_session_state()

        assert app._awaiting_gen_grade is False
        assert app._awaiting_recall_grade is False
        assert app._awaiting_advance is False
        assert app._pending_requeue is None
        assert app._current_item is None
        assert app._last_diff_markup == ""
        assert app.showing_stats is False

    def test_reset_clears_practice_mode(self):
        app = GenerationReviewApp(db_path=":memory:")
        app.practice_mode = True
        app.ordered_practice = True

        app._reset_session_state()

        assert app.practice_mode is False
        assert app.ordered_practice is False

    def test_reset_restores_original_start_level(self):
        app = GenerationReviewApp(db_path=":memory:", start_level=2)
        app.start_level = 0  # mutated during session

        app._reset_session_state()

        assert app.start_level == 2
