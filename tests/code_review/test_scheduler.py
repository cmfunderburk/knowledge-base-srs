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
    schedule,
)
from knowledge_base.srs.fsrs import Grade, initial_difficulty, initial_stability


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


def _learning_state(step_index: int = 0) -> CardState:
    return CardState(
        phase=Phase.LEARNING,
        step_index=step_index,
        stability=0.0,
        difficulty=0.0,
        reps=0,
        last_review=None,
        due=NOW.isoformat(),
    )


def _seconds_until(now: datetime, due_iso: str) -> int:
    due = datetime.fromisoformat(due_iso)
    return round((due - now).total_seconds())


def test_learning_again_resets_to_step_0_with_1m_delay():
    state = _learning_state(step_index=2)
    result = schedule(state, Grade.AGAIN, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 0
    assert _seconds_until(NOW, result.due) == 60


def test_learning_hard_repeats_current_step():
    state = _learning_state(step_index=1)  # 10m step
    result = schedule(state, Grade.HARD, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 1
    assert _seconds_until(NOW, result.due) == 600


def test_learning_good_advances_one_step():
    state = _learning_state(step_index=1)  # 10m → next is 4h step
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.LEARNING
    assert result.step_index == 2
    assert _seconds_until(NOW, result.due) == 14400


def test_learning_good_past_last_step_graduates_to_review():
    state = _learning_state(step_index=3)  # 12h step is last
    result = schedule(state, Grade.GOOD, NOW)
    assert result.phase == Phase.REVIEW
    assert result.stability == initial_stability(Grade.GOOD)
    assert result.difficulty == initial_difficulty(Grade.GOOD)
    # due is at least several days out, not minutes
    assert _seconds_until(NOW, result.due) > 86400


def test_learning_easy_graduates_immediately_from_any_step():
    for step in (0, 1, 2, 3):
        state = _learning_state(step_index=step)
        result = schedule(state, Grade.EASY, NOW)
        assert result.phase == Phase.REVIEW, f"step={step}"
        assert result.stability == initial_stability(Grade.EASY)
        assert result.difficulty == initial_difficulty(Grade.EASY)


def test_learning_grade_increments_reps_and_sets_last_review():
    state = _learning_state(step_index=0)
    result = schedule(state, Grade.GOOD, NOW)
    assert result.reps == 1
    assert result.last_review == NOW.isoformat()
