"""Adapter: wound-ignite's final configuration for one forecast origin (issue #19).

    uv run --project vendor/wound-ignite python run.py <prices.csv> <origin> <out.csv>
        [--seed N] [--constant-dre]

<prices.csv>: wide adjusted closes, first column the date, one column per asset of the
universe, rows up to the origin (written by tesina.models.external.PythonScriptModel).

What it reproduces (upstream ``combine/precise-combine.ipynb`` and
``submit/precise-submit.ipynb`` at commit c26cbc6, "month 11", the last configuration
the author committed):

- the eight covariance skaters ``BEST_F = [7, 21, 6, 23, 8, 61, 53, 22]`` of
  ``ALL_D0_SKATERS`` with portfolio ``PORT[0]`` and ``scale_w = 1``;
- for each, ``m6_competition_entry`` with ``last_date = origin`` (quintile probabilities
  by Monte Carlo from the estimated covariance, and portfolio weights);
- the submit notebook's combination: probabilities averaged, renormalised, rounded to
  5 decimals with ``Rank5`` as the remainder; weights averaged, rounded, and scaled up to
  a gross exposure of 0.251 if below 0.25.

Adaptations (documented in NOTICE.md):

- ``m6_data`` hard-codes the 100 M6 tickers and reads per-ticker CSVs from a cache
  folder; here it is replaced by the same logic over the universe passed in, from a
  cache folder written from <prices.csv>. Its padding of short histories (repeating the
  available prices) is kept.
- The Monte Carlo has no seed upstream; ``--seed`` makes runs reproducible.
- ``--constant-dre`` replaces DRE by a constant price, as the author's
  ``generate_dre.py`` did from month 10.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import precise.skatertools.m6.covarianceforecasting as covfc
from precise.skaters.covariance.allcovskaters import ALL_D0_SKATERS
from precise.skaters.portfoliostatic.allstaticport import PORT
from precise.skatertools.data.equitylive import get_prices
from precise.skatertools.m6.competition import m6_competition_entry

BEST_F = [7, 21, 6, 23, 8, 61, 53, 22]
BEST_PORT = [0] * len(BEST_F)
BEST_SCALING = [1] * len(BEST_F)
RANKS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]
DRE_PRICE = 48.20001  # upstream generate_dre.py


def patch_m6_data(tickers: list[str]) -> None:
    """Upstream ``m6_data`` with the ticker list passed in instead of the hard-coded one."""

    def m6_data(interval="d", n_dim=100, n_obs=300, last_date=None, cache_path=None):
        df = pd.DataFrame(columns=tickers)
        for ticker in tickers:
            closing_prices = get_prices(
                ticker=ticker,
                n_obs=n_obs + 1,
                interval=interval,
                last_date=last_date,
                cache_path=cache_path,
            )
            while len(closing_prices) < n_obs + 1:
                closing_prices = list(closing_prices) + list(closing_prices)
            closing_prices = closing_prices[-n_obs:]
            df[ticker] = np.diff(np.log(closing_prices))
        return df

    covfc.m6_data = m6_data


def write_cache(wide: pd.DataFrame, folder: Path, constant_dre: bool) -> None:
    for ticker in wide.columns:
        series = wide[ticker].dropna()
        if constant_dre and ticker == "DRE":
            series = pd.Series(DRE_PRICE, index=wide.index)
        pd.DataFrame(
            {"Date": series.index.strftime("%Y-%m-%d"), "Adj Close": series.to_numpy()}
        ).to_csv(folder / f"{ticker}.csv", index=False)


def combine(entries: list[pd.DataFrame]) -> pd.DataFrame:
    """Upstream submit notebook (probabilities and decisions)."""
    rps_sub = sum(e[RANKS] for e in entries) / len(entries)
    rps_sub = rps_sub / rps_sub.sum(axis=1).to_numpy()[:, np.newaxis]
    rps_sub = rps_sub.round(5)
    rps_sub["Rank5"] = 1 - rps_sub.drop(columns="Rank5").sum(axis=1)
    rps_sub = rps_sub.round(5)
    ir_sub = sum(e["Decision"] for e in entries) / len(entries)
    ir_sub = ir_sub.round(5)
    if ir_sub.abs().sum() < 0.25:
        ir_sub = ir_sub / (ir_sub.abs().sum() / 0.251)
        ir_sub = ir_sub.round(5)
    out = rps_sub.copy()
    out["Decision"] = ir_sub
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prices")
    parser.add_argument("origin")
    parser.add_argument("out")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--constant-dre", action="store_true")
    args = parser.parse_args()

    wide = pd.read_csv(args.prices, index_col=0, parse_dates=True)
    origin = pd.Timestamp(args.origin)
    wide = wide.loc[wide.index <= origin]
    tickers = list(wide.columns)
    patch_m6_data(tickers)
    np.random.seed(args.seed)
    with tempfile.TemporaryDirectory(prefix="wound_ignite_") as cache:
        write_cache(wide, Path(cache), args.constant_dre)
        entries = []
        for f, port, scaling in zip(BEST_F, BEST_PORT, BEST_SCALING, strict=True):
            entry = m6_competition_entry(
                f=ALL_D0_SKATERS[f],
                port=PORT[port],
                last_date=origin,
                scale_w=scaling,
                cache_path=cache,
                verbose=False,
            )
            entry.columns = [*RANKS, "Decision"]
            entries.append(entry)
    out = combine(entries).loc[tickers]
    out.rename_axis("ID").reset_index().to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
