# Polynomial via enumerate (QuantEcon 5.7.2)

Consider the polynomial

$$
p(x) = a_0 + a_1 x + a_2 x^2 + \cdots + a_n x^n = \sum_{i=0}^{n} a_i x^i
$$

Write a function `p(x, coeff)` that computes the value of $p(x)$ given a point `x` and a sequence of coefficients `coeff` $= (a_0, a_1, \dots, a_n)$.

Try to use `enumerate()` in your loop.
