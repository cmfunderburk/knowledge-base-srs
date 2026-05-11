from datetime import datetime, timezone

import pytest

from knowledge_base.code_review.leitner import LeitnerResult, schedule

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_again_resets_to_box_1():
    result = schedule(current_box=3, grade=1, now=NOW)
    assert result.box == 1
    assert result.interval == 1.0


def test_hard_stays_in_current_box():
    result = schedule(current_box=3, grade=2, now=NOW)
    assert result.box == 3
    assert result.interval == 4.0


def test_good_advances_one_box():
    result = schedule(current_box=2, grade=3, now=NOW)
    assert result.box == 3
    assert result.interval == 4.0


def test_easy_advances_two_boxes():
    result = schedule(current_box=2, grade=4, now=NOW)
    assert result.box == 4
    assert result.interval == 8.0


def test_good_caps_at_box_5():
    result = schedule(current_box=5, grade=3, now=NOW)
    assert result.box == 5
    assert result.interval == 16.0


def test_easy_caps_at_box_5():
    result = schedule(current_box=4, grade=4, now=NOW)
    assert result.box == 5
    assert result.interval == 16.0


def test_due_is_iso8601_string():
    result = schedule(current_box=1, grade=3, now=NOW)
    datetime.fromisoformat(result.due)  # should not raise


def test_naive_datetime_is_treated_as_utc():
    naive = datetime(2026, 1, 1)
    result = schedule(current_box=1, grade=3, now=naive)
    assert result.box == 2
