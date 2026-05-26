def p(x, coeff):
    return sum(a * x**i for i, a in enumerate(coeff))
