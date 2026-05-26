def linapprox(f, a, b, n, x):
    """
    Evaluate the piecewise linear interpolant of f at x on the interval [a, b],
    using n evenly spaced grid points.
    """
    length_of_interval = b - a
    num_subintervals = n - 1
    step = length_of_interval / num_subintervals

    # find first grid point larger than x
    point = a
    while point <= x:
        point += step

    # x lies between (point - step) and point
    u, v = point - step, point

    return f(u) + (x - u) * (f(v) - f(u)) / (v - u)
