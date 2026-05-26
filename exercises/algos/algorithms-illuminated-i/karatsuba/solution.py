def karatsuba(x, y):
    if x < 10 or y < 10:
        return x * y

    # split point: half the max digit count, rounded up
    n = max(len(str(x)), len(str(y)))
    half = n // 2

    divisor = 10 ** half
    a, b = divmod(x, divisor)
    c, d = divmod(y, divisor)

    ac = karatsuba(a, c)
    bd = karatsuba(b, d)
    ad_plus_bc = karatsuba(a + b, c + d) - ac - bd

    return ac * 10 ** (2 * half) + ad_plus_bc * 10 ** half + bd
