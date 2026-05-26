def x(t):
    if t == 0:
        return 0
    if t == 1:
        return 1
    return x(t - 1) + x(t - 2)
