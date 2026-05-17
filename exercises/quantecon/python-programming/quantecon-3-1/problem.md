# Correlated Time Series (QuantEcon 3.6.1)

Simulate and plot the correlated time series

    x_{t+1} = α · x_t + ε_{t+1}    where x_0 = 0,  t = 0, …, T

The sequence of shocks {ε_t} is IID standard normal.

Set T = 200 and α = 0.9. Name the time series array `x`.

Restrict your imports to:

    import numpy as np
    import matplotlib.pyplot as plt
