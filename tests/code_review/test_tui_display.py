from datetime import datetime, timedelta, timezone

from knowledge_base.code_review.tui import format_due_label


NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_format_due_label_minutes():
    due = (NOW + timedelta(minutes=8)).isoformat()
    assert format_due_label(due, NOW) == "due in 8m"


def test_format_due_label_hours():
    due = (NOW + timedelta(hours=3)).isoformat()
    assert format_due_label(due, NOW) == "due in 3h"


def test_format_due_label_days_returns_date():
    due = (NOW + timedelta(days=2)).isoformat()
    assert format_due_label(due, NOW) == "due 2026-05-20"


def test_format_due_label_overdue_shows_now():
    due = (NOW - timedelta(minutes=5)).isoformat()
    assert format_due_label(due, NOW) == "due now"


def test_format_due_label_null_returns_new():
    assert format_due_label(None, NOW) == "new"
