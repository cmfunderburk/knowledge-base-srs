import numpy as np
import matplotlib.pyplot as plt

α = 0.9
T = 200
x = np.empty(T + 1)
x[0] = 0
rng = np.random.default_rng()

for t in range(T):
    x[t + 1] = α * x[t] + rng.standard_normal()

plt.plot(x)
plt.show()
