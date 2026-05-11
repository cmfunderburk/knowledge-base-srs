# Correlated Time Series (QuantEcon 3.6.1)

Simulate the correlated time series

    x_{t+1} = α · x_t + ε_{t+1}    where x_0 = 0,  t = 0, …, T

The sequence of shocks {ε_t} is IID standard normal. Set T = 200 and α = 0.9.

## Your submission must define this function

```python
def simulate(alpha: float, T: int, rng: np.random.Generator) -> np.ndarray:
    ...  # return array of length T + 1, with x[0] = 0
```

You may also add plotting code (e.g. `plt.plot(x); plt.show()`) outside the function,
but the function itself is what the tests check.

## Imports

```python
import numpy as np
import matplotlib.pyplot as plt
```
