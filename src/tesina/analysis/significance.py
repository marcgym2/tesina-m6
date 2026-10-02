"""Paired tests of forecast accuracy against a benchmark (issue #26).

Input: a loss differential per evaluation period, ``d_t = loss_model,t -
loss_benchmark,t`` (e.g. RPS). Negative mean = the model beats the benchmark.

- ``diebold_mariano``: DM test (Diebold & Mariano, 1995) with the small-sample
  correction of Harvey, Leybourne & Newbold (1997) and Student-t(T-1) critical values.
  Four-week periods do not overlap (horizon h = 1 period), so the long-run variance
  uses autocovariances up to lag h - 1.
- ``block_bootstrap``: circular block bootstrap of the mean differential, as a
  robustness check that does not rely on the t approximation.
- ``adjust_pvalues``: Holm (family-wise error) and Benjamini-Hochberg (false
  discovery rate) adjustments for multiple comparisons.

A differential that is identically zero (the model equals the benchmark) gives no
evidence either way: statistic NaN and p-value 1.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

ALTERNATIVES = ("less", "greater", "two-sided")


def _check(d, alternative: str) -> np.ndarray:
    if alternative not in ALTERNATIVES:
        raise ValueError(f"unknown alternative {alternative!r}")
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    if len(d) < 3:
        raise ValueError("need at least 3 periods")
    return d


def _p_from_t(t: float, df: int, alternative: str) -> float:
    if alternative == "less":
        return float(stats.t.cdf(t, df))
    if alternative == "greater":
        return float(stats.t.sf(t, df))
    return float(2 * stats.t.sf(abs(t), df))


def diebold_mariano(d, h: int = 1, alternative: str = "less") -> dict:
    """DM-HLN test of ``E[d] = 0``; ``alternative="less"``: the model has lower loss."""
    d = _check(d, alternative)
    n = len(d)
    mean = float(d.mean())
    centered = d - mean
    gamma = [float(centered[k:] @ centered[: n - k]) / n for k in range(h)]
    long_run_var = gamma[0] + 2 * sum(gamma[1:])
    out = {"n": n, "mean_diff": mean, "h": h, "alternative": alternative}
    if long_run_var <= 0:
        return {**out, "dm_stat": float("nan"), "p_value": 1.0}
    dm = mean / np.sqrt(long_run_var / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = float(dm * hln)
    return {**out, "dm_stat": stat, "p_value": _p_from_t(stat, n - 1, alternative)}


def block_bootstrap(
    d,
    block: int = 2,
    n_boot: int = 10_000,
    seed: int = 0,
    alternative: str = "less",
    level: float = 0.95,
) -> dict:
    """Circular block bootstrap of the mean differential.

    The p-value resamples the centred series (null imposed); the interval resamples
    the raw series (percentile method).
    """
    d = _check(d, alternative)
    n = len(d)
    mean = float(d.mean())
    if np.ptp(d) == 0:
        return {"n": n, "mean_diff": mean, "p_boot": 1.0, "ci_low": mean, "ci_high": mean}
    rng = np.random.default_rng(seed)
    n_blocks = -(-n // block)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n] % n
    boot_raw = d[idx].mean(axis=1)
    boot_null = (d - mean)[idx].mean(axis=1)
    if alternative == "less":
        hits = np.sum(boot_null <= mean)
    elif alternative == "greater":
        hits = np.sum(boot_null >= mean)
    else:
        hits = np.sum(np.abs(boot_null) >= abs(mean))
    alpha = (1 - level) / 2
    low, high = np.quantile(boot_raw, [alpha, 1 - alpha])
    return {
        "n": n,
        "mean_diff": mean,
        "p_boot": float((hits + 1) / (n_boot + 1)),
        "ci_low": float(low),
        "ci_high": float(high),
    }


def adjust_pvalues(p, method: str = "holm") -> np.ndarray:
    """Holm step-down or Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(p, dtype=float)
    if method == "holm":
        order = np.argsort(p)
        m = len(p)
        adjusted = np.maximum.accumulate((m - np.arange(m)) * p[order]).clip(max=1)
        out = np.empty(m)
        out[order] = adjusted
        return out
    if method == "bh":
        return stats.false_discovery_control(p, method="bh")
    raise ValueError(f"unknown method {method!r}")
