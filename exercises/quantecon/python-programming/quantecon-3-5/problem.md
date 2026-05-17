# Monte Carlo π Approximation (QuantEcon 3.5)

Compute an approximation to π using Monte Carlo.

Sample points uniformly on the unit square (0, 1)². The fraction that fall
inside the inscribed circle of radius 0.5 centred at (0.5, 0.5) approximates
the area of that circle, which equals π · 0.5². So π ≈ 4 · (fraction inside).

Store your estimate in a variable named `pi_estimate`.

Restrict your imports to:

    import numpy as np

Hints:

- If U is a bivariate uniform random variable on the unit square (0, 1)²,
  then the probability that U lies in a subset B is equal to the area of B.
- If U_1, …, U_n are IID copies of U, then as n grows the fraction landing
  in B converges to the probability of landing in B.
- For a circle, area = π · radius².
