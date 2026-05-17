# Binomial Random Variable (QuantEcon 4.2)

The binomial random variable Y ~ Bin(n, p) represents the number of
successes in n binary trials, where each trial succeeds with probability p.

Using `rng = np.random.default_rng()`, write a function `binomial_rv` such
that `binomial_rv(n, p)` generates one draw of Y.

Restrict your imports to:

    import numpy as np

Hint:

- If U is uniform on (0, 1) and p ∈ (0, 1), then the expression `U < p`
  evaluates to True with probability p.
