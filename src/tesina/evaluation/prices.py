"""Price windows for one M6 evaluation period.

Reference: ``RPS and IR calculation.R`` / ``.py`` in Mcompetitions/M6-methods
(commit 10c553f). The eligible days are the dates present in the price data between
the first and last date of the period, and a missing price is filled with the
previous available price of the same asset.

The two official scripts differ on where that previous price may come from: the R
script only fills within the window, the Python script looks back over the whole
price history. The official leaderboard follows the Python behaviour: DRE stopped
trading on 2022-11-28, yet months 11-12 are scored with 100 assets and DRE held at its
last price (verified against every team in ``summary_leaderboard.xlsx``; see
tests/test_evaluation.py). The whole-history fill is used here.
"""

from __future__ import annotations

import pandas as pd


def period_prices(prices: pd.DataFrame, base_date, end_date) -> pd.DataFrame:
    """Wide price matrix (eligible days x symbols) for one evaluation period.

    ``prices`` is long format with columns ``symbol``, ``date``, ``price``.
    ``base_date`` is the last trading day before the period (returns are measured
    from its close) and ``end_date`` the last trading day of the period. Columns are
    every symbol with a price on or before ``end_date``; missing prices are filled
    with the symbol's last earlier price. Only data up to ``end_date`` is used.
    """
    base_date, end_date = pd.Timestamp(base_date), pd.Timestamp(end_date)
    history = prices[prices["date"] <= end_date]
    # pivot (not pivot_table) so duplicated (date, symbol) rows raise instead of averaging.
    wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    wide = wide.sort_index().ffill()
    wide = wide.loc[wide.index >= base_date]
    if wide.empty or wide.index[0] != base_date or wide.index[-1] != end_date:
        raise ValueError(
            f"{base_date.date()} and {end_date.date()} must be dates present in the price data"
        )
    return wide


def period_returns(wide: pd.DataFrame) -> pd.Series:
    """Simple return of each asset from the base date to the end of the period."""
    return (wide.iloc[-1] - wide.iloc[0]) / wide.iloc[0]


def daily_returns(wide: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns on the eligible days (the base date is dropped)."""
    return (wide.diff() / wide.shift(1)).iloc[1:]
