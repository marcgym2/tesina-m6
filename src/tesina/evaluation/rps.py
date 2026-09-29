"""Ranked Probability Score (RPS) of M6 quintile forecasts.

Reimplementation of ``RPS_calculation`` in ``RPS and IR calculation.R``
(Mcompetitions/M6-methods, commit 10c553f), cross-checked against the official
worked example (``Evaluation - example.xlsx``) and the official leaderboard.

Rules (from the official R code):

1. Each asset's return over the period is ranked in ascending order with ties
   getting the minimum rank (``rank(ties.method = "min")``): position 1 is the
   worst return.
2. Positions 1-20 are quintile 1, 21-40 quintile 2, ..., 81-100 quintile 5.
3. Ties: a group of ``c`` tied assets at position ``p`` spans positions
   ``p .. p + c - 1``; every asset in the group gets the average of the one-hot
   quintile vectors of those positions (so the target can be fractional).
4. Per asset, RPS = mean over the 5 quintiles of the squared difference between
   the cumulative target and the cumulative forecast; the period RPS is the mean
   over assets.

Note: the official Python script differs on rule 3 (an ``elif`` assigns a tie group
that straddles two quintiles only to the first one, so the target no longer sums
to 1). The R code is followed here; for untied returns both agree.

The official code hard-codes the thresholds 20/40/60/80, i.e. it assumes 100 assets
(in period 1 the universe always has 100, see ``prices.period_prices``). Any other
size is rejected unless ``n_assets_rule="proportional"`` (thresholds ``k * n / 5``) is
chosen explicitly; that choice belongs to issue #11 and is not part of the official code.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RANK_COLUMNS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]


OFFICIAL_THRESHOLDS = np.array([20, 40, 60, 80])


def quintile_targets(returns: pd.Series, n_assets_rule: str = "official") -> pd.DataFrame:
    """Observed quintile distribution per asset (rows sum to 1), following the R code."""
    if returns.isna().any():
        missing = list(returns.index[returns.isna()])
        raise ValueError(f"missing period returns for {missing}")
    n = len(returns)
    if n_assets_rule == "official":
        if n != 100:
            raise ValueError(f"official quintile thresholds assume 100 assets, got {n}")
        thresholds = OFFICIAL_THRESHOLDS
    elif n_assets_rule == "proportional":
        thresholds = np.array([k * n / 5 for k in range(1, 5)])
    else:
        raise ValueError(f"unknown n_assets_rule {n_assets_rule!r}")
    position = returns.rank(method="min").astype(int)
    counts = position.value_counts()

    targets = pd.DataFrame(0.0, index=returns.index, columns=RANK_COLUMNS)
    for start, count in counts.items():
        spanned = np.arange(start, start + count)
        quintile = np.searchsorted(thresholds, spanned, side="left")  # 0..4
        share = np.bincount(quintile, minlength=5) / count
        targets.loc[position.index[position == start]] = share
    return targets


def rps_per_asset(forecast: pd.DataFrame, targets: pd.DataFrame) -> pd.Series:
    """RPS of each asset. Both frames are indexed by symbol with columns Rank1..Rank5."""
    missing = targets.index.difference(forecast.index)
    if len(missing):
        raise ValueError(f"forecast missing assets: {list(missing)}")
    f = forecast.loc[targets.index, RANK_COLUMNS].to_numpy(dtype=float).cumsum(axis=1)
    t = targets[RANK_COLUMNS].to_numpy(dtype=float).cumsum(axis=1)
    return pd.Series(((t - f) ** 2).mean(axis=1), index=targets.index, name="RPS")


def rps(forecast: pd.DataFrame, returns: pd.Series, n_assets_rule: str = "official") -> float:
    """Period RPS of a submission given each asset's return over the period."""
    targets = quintile_targets(returns, n_assets_rule)
    return float(rps_per_asset(forecast, targets).mean())
