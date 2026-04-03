"""Tests for the massed practice reshuffling algorithm."""

import random

from knowledge_base.srs.generation_tui import massed_requeue_position


class TestMassedRequeuePosition:
    def test_fail_returns_1(self):
        assert massed_requeue_position(passed=False, pass_count=0, queue_len=10) == 1

    def test_first_pass_in_range_2_4(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=1, queue_len=20)
                     for _ in range(100)}
        assert positions <= {2, 3, 4}
        assert len(positions) > 1

    def test_second_pass_in_range_4_8(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=2, queue_len=20)
                     for _ in range(100)}
        assert positions <= {4, 5, 6, 7, 8}
        assert len(positions) > 1

    def test_third_pass_in_range_8_12(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=3, queue_len=20)
                     for _ in range(100)}
        assert positions <= {8, 9, 10, 11, 12}
        assert len(positions) > 1

    def test_fourth_plus_pass_in_range_8_12(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=5, queue_len=20)
                     for _ in range(100)}
        assert positions <= {8, 9, 10, 11, 12}

    def test_clamped_to_queue_length(self):
        pos = massed_requeue_position(passed=True, pass_count=3, queue_len=3)
        assert pos == 3

    def test_masking_level_pass_uses_first_range(self):
        random.seed(42)
        positions = {massed_requeue_position(passed=True, pass_count=0, queue_len=20)
                     for _ in range(100)}
        assert positions <= {2, 3, 4}
