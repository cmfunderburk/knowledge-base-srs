def count_even_pairs(pairs):
    return sum(a % 2 == 0 and b % 2 == 0 for a, b in pairs)
