import numpy as np
import matplotlib.pyplot as plt


def simulate(alpha: float, T: int, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(T + 1)
    x[0] = 0.0
    for t in range(T):
        x[t + 1] = alpha * x[t] + rng.standard_normal()
    return x


if __name__ == "__main__":
    alpha = 0.9
    T = 200
    rng = np.random.default_rng()
    x = simulate(alpha, T, rng)
    plt.plot(x)
    plt.show()
