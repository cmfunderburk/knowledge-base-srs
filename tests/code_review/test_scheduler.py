from datetime import datetime, timedelta, timezone

import pytest

from knowledge_base.code_review.scheduler import (
    CardState,
    LEARNING_STEPS_SEC,
    LEARN_AHEAD_SEC,
    Phase,
    RELEARNING_STEPS_SEC,
    DESIRED_RETENTION,
    initial_state,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_constants_match_anki_config():
    assert LEARNING_STEPS_SEC == [60, 600, 14400, 43200]
    assert RELEARNING_STEPS_SEC == [1800, 14400]
    assert LEARN_AHEAD_SEC == 1200
    assert DESIRED_RETENTION == 0.95


def test_phase_enum_values():
    assert Phase.LEARNING == 1
    assert Phase.REVIEW == 2
    assert Phase.RELEARNING == 3


def test_initial_state_fresh_card():
    state = initial_state(NOW)
    assert state.phase == Phase.LEARNING
    assert state.step_index == 0
    assert state.stability == 0.0
    assert state.difficulty == 0.0
    assert state.reps == 0
    assert state.last_review is None
    assert state.due == NOW.isoformat()
