# Empirical CDF (QuantEcon 8.5.1)

The empirical cumulative distribution function (ecdf) corresponding to a sample $\{X_i\}_{i=1}^{n}$ is defined as

$$
F_n(x) := \frac{1}{n} \sum_{i=1}^{n} \mathbf{1}\{X_i \le x\}, \quad (x \in \mathbb{R})
$$

Here $\mathbf{1}\{X_i \le x\}$ is an indicator function (one if $X_i \le x$, zero otherwise), so $F_n(x)$ is the fraction of the sample at or below $x$.

Implement $F_n$ as a class called `ECDF`, where

- A given sample $\{X_i\}_{i=1}^{n}$ are the instance data, stored as `self.observations`.
- The class implements a `__call__` method that returns $F_n(x)$ for any $x$.

Your code should work as follows (modulo randomness):

    from random import uniform

    samples = [uniform(0, 1) for i in range(10)]
    F = ECDF(samples)
    F(0.5)                  # evaluate ecdf at x = 0.5

    F.observations = [uniform(0, 1) for i in range(1000)]
    F(0.5)

Aim for clarity, not efficiency.
