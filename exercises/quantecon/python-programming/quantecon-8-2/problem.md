# Polynomial Class (QuantEcon 8.5.2)

In an earlier exercise (5.7.2), you wrote a function for evaluating polynomials. This exercise is an extension: build a simple class called `Polynomial` for representing and manipulating polynomial functions

$$
p(x) = a_0 + a_1 x + a_2 x^2 + \cdots + a_N x^N = \sum_{n=0}^{N} a_n x^n
$$

The instance data for `Polynomial` will be the coefficients $(a_0, \dots, a_N)$, stored as `self.coefficients`.

Provide methods that

1. Evaluate the polynomial, returning $p(x)$ for any $x$. (Implement this as `__call__` so the instance is callable.)
2. Differentiate the polynomial in place: replace `self.coefficients` with those of its derivative $p'$. Name this method `differentiate`. It should also return the new coefficients.

**Avoid using any `import` statements.**
