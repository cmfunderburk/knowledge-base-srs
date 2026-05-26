# Karatsuba Multiplication (Algorithms Illuminated, Part I)

Implement **Karatsuba multiplication** — Anatoly Karatsuba's 1960 divide-and-conquer algorithm that multiplies two `n`-digit integers in $\Theta(n^{\log_2 3}) \approx \Theta(n^{1.585})$ time.

## The Algorithm

Given two non-negative integers `x` and `y` with at most `n` digits each, split them in half:

$$
x = 10^{n/2} \cdot a + b, \qquad y = 10^{n/2} \cdot c + d
$$

Then

$$
x \cdot y = 10^n \cdot (ac) + 10^{n/2} \cdot (ad + bc) + bd
$$

The clever step is computing `ad + bc` with **one** recursive multiplication instead of two:

$$
(a + b)(c + d) = ac + ad + bc + bd \;\Rightarrow\; ad + bc = (a + b)(c + d) - ac - bd
$$

So each level of recursion needs only **three** multiplications of half-size numbers (`ac`, `bd`, and `(a+b)(c+d)`) rather than four.

## Requirements

Expose a top-level function:

- `karatsuba(x, y) -> int` — returns `x * y` for non-negative integers `x` and `y`.

Constraints:

- **Recursive divide-and-conquer with the three-multiplication trick.** A bare `return x * y` defeats the purpose and will fail tests.
- A base case of single-digit numbers (`x < 10 or y < 10`) is fine — at the base case you may use Python's built-in `*`.
- Standard library only.
- `karatsuba(0, anything)` and `karatsuba(anything, 0)` should return `0`.

You only need to handle non-negative integers.
