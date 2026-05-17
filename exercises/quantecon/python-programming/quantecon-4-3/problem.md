# Coin-Flip Payoff Devices (QuantEcon 4.3)

Write two functions that each return one realization (0 or 1) of a random
payoff device based on 10 flips of an unbiased coin.

**First device — `draw(k)`** (consecutive heads):

1. Flip an unbiased coin 10 times.
2. If a head occurs `k` or more times *consecutively* within this sequence
   at least once, pay one dollar.
3. If not, pay nothing.

**Second device — `draw_new(k)`** (total heads):

Same as above except rule 2 becomes:

- If a head occurs `k` or more times within this sequence (in total), pay
  one dollar.

Each function should return `1` (paid) or `0` (not paid).

Use `rng = np.random.default_rng()` to generate random numbers.

Restrict your imports to:

    import numpy as np
