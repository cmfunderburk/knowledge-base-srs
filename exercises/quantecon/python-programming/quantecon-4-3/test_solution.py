import sys

import numpy as np
import pytest


@pytest.fixture
def sub():
    """Fresh import of submission.py for each test."""
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_runs_without_error(sub):
    pass


def test_draw_exists(sub):
    assert hasattr(sub, "draw"), "solution must define a function named 'draw' (consecutive-heads device)"
    assert callable(sub.draw)


def test_draw_new_exists(sub):
    assert hasattr(sub, "draw_new"), "solution must define a function named 'draw_new' (total-heads device)"
    assert callable(sub.draw_new)


def test_draw_returns_zero_or_one(sub):
    for _ in range(100):
        y = sub.draw(3)
        assert y in (0, 1), f"draw(3) returned {y!r}; expected 0 or 1"


def test_draw_new_returns_zero_or_one(sub):
    for _ in range(100):
        y = sub.draw_new(3)
        assert y in (0, 1), f"draw_new(3) returned {y!r}; expected 0 or 1"


def test_draw_impossible_k_always_zero(sub):
    # 10 flips can produce at most 10 consecutive heads, so k=11 is impossible.
    for _ in range(50):
        assert sub.draw(11) == 0, "draw(k) with k > 10 must always return 0"


def test_draw_new_impossible_k_always_zero(sub):
    for _ in range(50):
        assert sub.draw_new(11) == 0, "draw_new(k) with k > 10 must always return 0"


def test_draw_k_one_pays_often(sub):
    # P(at least one head in 10 flips) = 1 - 0.5^10 ≈ 0.999
    payoffs = [sub.draw(1) for _ in range(200)]
    rate = np.mean(payoffs)
    assert rate > 0.9, (
        f"draw(1) paid only {rate:.2%} of the time; expected ≈ 99.9% "
        f"(any single head triggers payoff)"
    )


def test_draw_new_k_one_pays_often(sub):
    payoffs = [sub.draw_new(1) for _ in range(200)]
    rate = np.mean(payoffs)
    assert rate > 0.9, (
        f"draw_new(1) paid only {rate:.2%} of the time; expected ≈ 99.9% "
        f"(any single head triggers payoff)"
    )


def test_draw_pay_rate_k_three(sub):
    # P(run of >=3 heads in 10 flips) ≈ 0.508 (known value).
    payoffs = [sub.draw(3) for _ in range(1000)]
    rate = np.mean(payoffs)
    # Wide tolerance to keep the test stable across RNGs.
    assert 0.35 < rate < 0.65, (
        f"draw(3) paid {rate:.3f} of the time; expected ≈ 0.51 "
        f"— check the 'consecutive' run-length logic (streak should reset on tails)"
    )


def test_draw_new_pay_rate_k_three(sub):
    # P(total heads >= 3 in 10 flips) ≈ 0.945.
    payoffs = [sub.draw_new(3) for _ in range(1000)]
    rate = np.mean(payoffs)
    assert rate > 0.85, (
        f"draw_new(3) paid {rate:.3f} of the time; expected ≈ 0.95 "
        f"— check the 'total heads' logic (count should not reset on tails)"
    )


def test_draw_new_dominates_draw(sub):
    # A run of k consecutive heads implies >= k total heads, so the total-heads
    # device must pay at least as often as the consecutive-heads device in
    # expectation. Catches mixing up the two rules.
    n = 1000
    consec = np.mean([sub.draw(4) for _ in range(n)])
    total = np.mean([sub.draw_new(4) for _ in range(n)])
    assert total > consec - 0.05, (
        f"draw_new(4)={total:.3f} should pay at least as often as draw(4)={consec:.3f}; "
        f"functions may be swapped"
    )


def test_draw_k_ten_rare(sub):
    # P(10 consecutive heads in 10 flips) = 0.5^10 ≈ 0.001 — usually 0 over 200 trials.
    payoffs = [sub.draw(10) for _ in range(200)]
    rate = np.mean(payoffs)
    assert rate < 0.05, (
        f"draw(10) paid {rate:.3f} of the time; expected ≈ 0.001 "
        f"(only all-heads should pay)"
    )
