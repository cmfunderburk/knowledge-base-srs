# Piecewise Linear Interpolation (QuantEcon 5.7.5)

When we cover the numerical libraries, we will see they include many alternatives for interpolation and function approximation. Nevertheless, let's write our own function approximation routine as an exercise.

In particular, **without using any imports**, write a function `linapprox` that takes as arguments

- A function `f` mapping some interval $[a, b]$ into $\mathbb{R}$.
- Two scalars `a` and `b` providing the limits of this interval.
- An integer `n` determining the number of grid points.
- A number `x` satisfying `a <= x <= b`.

and returns the piecewise linear interpolation of `f` at `x`, based on `n` evenly spaced grid points

    a = point[0] < point[1] < ... < point[n-1] = b.

Aim for clarity, not efficiency.
