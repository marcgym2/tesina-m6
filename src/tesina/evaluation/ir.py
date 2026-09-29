"""Information Ratio (IR) of M6 investment decisions.

Reimplementation of ``IR_calculation`` in ``RPS and IR calculation.R``
(Mcompetitions/M6-methods, commit 10c553f), cross-checked against the official
worked example (``Evaluation - example.xlsx``) and the official leaderboard.

Rules:

1. On every eligible day ``t`` of the period, the portfolio return is
   ``sum_i w_i * r_{i,t}`` with ``r_{i,t}`` the simple daily return of asset ``i``
   and ``w_i`` the submitted weight (weights are held constant, i.e. rebalanced daily).
2. ``ret_t = log(1 + portfolio return)``.
3. ``IR = sum_t ret_t / sd(ret_t)`` with the sample standard deviation (n - 1).
4. Quarterly and global IR (worked example, sheet "Summary") pool the daily
   ``ret_t`` of all months involved and apply rule 3 to the pooled series.

Zero variance: a portfolio whose daily returns are all equal (in period 1, team
bc4b0314 put 100% of its weight on DRE, frozen after its merger, in months 10-12)
gives 0/0. The official code returns NaN; the official leaderboard shows IR = 1.0
for those months, a rule not present in the published code. The default follows
the code; ``zero_variance=1.0`` reproduces the leaderboard.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from tesina.evaluation.prices import daily_returns


def portfolio_log_returns(wide: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Daily log returns of the portfolio over one period.

    ``wide`` is the period price matrix (see ``prices.period_prices``); ``weights``
    is indexed by symbol. A NaN return (e.g. no base price) propagates, as in R.
    """
    missing = wide.columns.difference(weights.index)
    if len(missing):
        raise ValueError(f"weights missing assets: {list(missing)}")
    daily = daily_returns(wide)
    port = daily.mul(weights.loc[wide.columns], axis=1).sum(axis=1, skipna=False)
    return np.log1p(port).rename("ret")


def information_ratio(
    log_returns: pd.Series | Iterable[pd.Series], zero_variance: float = np.nan
) -> float:
    """IR of one period's daily log returns, or of several periods pooled together."""
    if not isinstance(log_returns, pd.Series):
        log_returns = pd.concat(list(log_returns))
    sd = log_returns.std(ddof=1)
    if sd == 0:
        return float(zero_variance)
    return float(log_returns.sum() / sd)
