import numpy as np


def simulate(alpha: float, T: int, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(T + 1)
    x[0] = 0.0
    for t in range(T):
        x[t + 1] = alpha * x[t] + rng.standard_normal()
    return x
