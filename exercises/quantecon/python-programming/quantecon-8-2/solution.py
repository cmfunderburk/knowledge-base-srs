class Polynomial:

    def __init__(self, coefficients):
        """
        p(x) = a_0 + a_1 x + ... + a_N x^N, where a_i = coefficients[i].
        """
        self.coefficients = coefficients

    def __call__(self, x):
        y = 0
        for i, a in enumerate(self.coefficients):
            y += a * x**i
        return y

    def differentiate(self):
        new_coefficients = []
        for i, a in enumerate(self.coefficients):
            new_coefficients.append(i * a)
        # remove the first element, which is always zero
        del new_coefficients[0]
        self.coefficients = new_coefficients
        return new_coefficients
