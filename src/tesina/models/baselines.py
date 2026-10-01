"""Baseline models (issue #16).

Both baselines hold the M6 investment benchmark (equal weights, 1/n per asset; 0.01
for the 100 M6 assets as in the official template) so that they differ only in their
forecasts.

- ``Uniform``: probability 0.2 for every quintile (the M6 forecasting benchmark).
- ``HistoricalFrequency``: for each asset, the frequency of each quintile in past
  four-week windows ending at the origin, with additive (Laplace) smoothing. Each past
  window ranks its returns cross-sectionally among the assets priced in it (rule 3 of
  CLAUDE.md), and every window ends on or before the origin, so no label overlaps the
  forecast period. Fixed hyper-parameters, chosen before looking at any result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tesina.evaluation.calendar import PERIOD_DAYS
from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import quintile_targets
from tesina.models import RANK_COLUMNS, Forecast


def equal_weights(universe: list[str]) -> pd.Series:
    return pd.Series(1.0 / len(universe), index=universe)


@dataclass
class Uniform:
    name: str = "uniform"

    def forecast(self, history, universe, origin) -> Forecast:
        probs = pd.DataFrame(0.2, index=universe, columns=RANK_COLUMNS)
        return Forecast(probs, equal_weights(universe))


def past_windows(trading_days: pd.DatetimeIndex, origin, lookback: int | None) -> list:
    """Past windows ``(base_date, end_date)`` of four weeks ending at ``origin``.

    Nominal boundaries step back 28 days from ``origin`` and map to the last trading
    day on or before each one. Windows without a trading day at their start are
    dropped, as is any window older than ``lookback`` (``None`` = all).
    """
    origin = pd.Timestamp(origin)
    windows = []
    j = 0
    while lookback is None or j < lookback:
        end_nominal = origin - pd.Timedelta(days=PERIOD_DAYS * j)
        base_nominal = end_nominal - pd.Timedelta(days=PERIOD_DAYS)
        b = trading_days.searchsorted(base_nominal, side="right") - 1
        e = trading_days.searchsorted(end_nominal, side="right") - 1
        if b < 0 or e <= b:
            break
        windows.append((trading_days[b], trading_days[e]))
        j += 1
    return windows


@dataclass
class HistoricalFrequency:
    lookback: int | None = None  # number of past windows; None = expanding
    alpha: float = 1.0  # additive smoothing per quintile
    name: str = "historical_frequency"

    def forecast(self, history, universe, origin) -> Forecast:
        history = history[history["symbol"].isin(universe)]
        wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        wide = wide.sort_index().ffill()
        counts = pd.DataFrame(0.0, index=universe, columns=RANK_COLUMNS)
        for base, end in past_windows(wide.index, origin, self.lookback):
            returns = period_returns(wide.loc[base:end]).dropna()
            if len(returns) < 5:
                continue
            counts.loc[returns.index] += quintile_targets(returns, "proportional").to_numpy()
        smoothed = counts + self.alpha
        totals = smoothed.sum(axis=1)
        probs = smoothed.div(totals.where(totals > 0, np.nan), axis=0)
        probs = probs.fillna(0.2)  # no history and alpha = 0: uniform
        return Forecast(probs, equal_weights(universe))
