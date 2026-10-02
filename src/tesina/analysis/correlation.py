"""Correlation estimates with bootstrap intervals and permutation p-values."""

from __future__ import annotations

import numpy as np
from scipy import stats

METHODS = {
    "spearman": lambda x, y: stats.spearmanr(x, y).statistic,
    "pearson": lambda x, y: stats.pearsonr(x, y).statistic,
}


def correlation(
    x,
    y,
    method: str = "spearman",
    n_boot: int = 10_000,
    n_perm: int = 10_000,
    level: float = 0.95,
    seed: int = 0,
) -> dict:
    """Correlation of paired observations with a percentile bootstrap CI.

    The interval resamples pairs with replacement; the two-sided p-value comes from
    permuting ``y`` (null: no association). Pairs with a missing value are dropped.
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    n = len(x)
    if n < 4:
        raise ValueError("need at least 4 complete pairs")
    stat = METHODS[method]
    rng = np.random.default_rng(seed)
    estimate = float(stat(x, y))

    idx = rng.integers(0, n, size=(n_boot, n))
    boot = np.array([stat(x[i], y[i]) for i in idx])
    boot = boot[np.isfinite(boot)]  # resamples with a constant column
    alpha = (1 - level) / 2
    low, high = np.quantile(boot, [alpha, 1 - alpha])

    perm = np.array([stat(x, rng.permutation(y)) for _ in range(n_perm)])
    p_value = (np.sum(np.abs(perm) >= abs(estimate)) + 1) / (n_perm + 1)
    return {
        "method": method,
        "n": n,
        "estimate": estimate,
        "ci_low": float(low),
        "ci_high": float(high),
        "level": level,
        "p_perm": float(p_value),
        "n_boot": n_boot,
        "n_perm": n_perm,
        "seed": seed,
    }
