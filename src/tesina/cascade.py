"""Bias cascade (RQ4, issues #24 and #25, decisions D5, D6 and D11).

The model is always the multiclass GBM of ``tesina.models.gbm``; what changes from one
step to the next is the procedure around it. The cascade starts from a naive pipeline
that commits every bias and removes them one at a time, in a fixed order:

- ``s0`` naive: rows shuffled into K folds over the whole sample (the model that
  forecasts a period was trained on rows from its future); weekly samples whose
  four-week labels overlap; features standardised per asset with full-sample statistics;
  the configuration reported is the best of the grid on the evaluation periods
  themselves; survivors' universe; no costs.
- ``s1`` temporal split: at each origin the model is trained only on samples whose base
  date is before the origin. Labels are still not purged: the last weekly samples have
  labels that run past the origin.
- ``s2`` purge: training uses only four-week windows that end on or before the origin
  (the non-overlapping windows of the clean model).
- ``s3`` past-only preprocessing: features become same-date cross-sectional ranks
  (no statistic fitted across time).
- ``s4`` honest selection: hyper-parameters chosen on past validation windows only (the
  clean GBM procedure); a single configuration per origin, nothing picked ex post.
- ``s5`` point-in-time universe (decision D2) instead of the survivors' universe.
- ``s6`` transaction costs on turnover: the clean model, net.

The survivors' universe (decision D6) is the M6 list with each delisted asset replaced
by its successor, a choice only possible after the fact: DRE->PLD, WRK->SW, AVB->VMRK.

Every step produces quintile probabilities per origin; weights are always the
expected-rank tilt, and scoring is the common walk-forward harness. Steps s0-s3 fit a
grid of configurations and report the one with the best RPS on the evaluation periods
(``select_ex_post``); the full grid is returned so the search can be reported.
"""

from __future__ import annotations

from itertools import product

import lightgbm as lgb
import numpy as np
import pandas as pd

from tesina.evaluation.rps import quintile_targets
from tesina.models import RANK_COLUMNS
from tesina.models.baselines import past_windows
from tesina.models.gbm import (
    DEFAULT_GRID,
    FEATURES,
    FIXED_PARAMS,
    cross_sectional_features,
    price_signals,
)

SUCCESSORS = {"DRE": "PLD", "WRK": "SW", "AVB": "VMRK"}
ROUNDS = (50, 100, 200)
LABEL_DAYS = 28


def survivors_universe(assets: list[str]) -> list[str]:
    return sorted(SUCCESSORS.get(a, a) for a in assets)


def configs(grid: dict | None = None) -> list[dict]:
    grid = grid or DEFAULT_GRID
    keys = sorted(grid)
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[k] for k in keys))]


def to_wide(prices: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    p = prices[prices["symbol"].isin(symbols)]
    wide = p.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    return wide.sort_index().ffill().reindex(columns=symbols)


def naive_features(wide: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Signals standardised per asset with the mean and deviation of the WHOLE sample,
    future included (the bias of fitting a scaler on all the data)."""
    return {name: (s - s.mean()) / s.std() for name, s in price_signals(wide).items()}


def forward_end(index: pd.DatetimeIndex, base: pd.Timestamp) -> pd.Timestamp | None:
    nominal = base + pd.Timedelta(days=LABEL_DAYS)
    if nominal > index[-1]:
        return None
    return index[index.searchsorted(nominal, side="right") - 1]


def sample(wide: pd.DataFrame, features: dict, base, end) -> pd.DataFrame | None:
    """Rows (one per asset) of a window: features at ``base``, quintile target to ``end``."""
    returns = (wide.loc[end] / wide.loc[base] - 1).dropna()
    if len(returns) < 5:
        return None
    x = pd.DataFrame({name: features[name].loc[base, returns.index] for name in FEATURES})
    targets = quintile_targets(returns, "proportional")
    return pd.concat([x, targets], axis=1).assign(base=base, end=end).rename_axis("symbol")


def weekly_dataset(wide: pd.DataFrame, features: dict, origins, step: int = 5) -> pd.DataFrame:
    """Samples every ``step`` trading days plus the evaluation origins, whole sample."""
    bases = set(wide.index[::step]) | {pd.Timestamp(o) for o in origins}
    rows = []
    for base in sorted(bases):
        end = forward_end(wide.index, base)
        if end is not None:
            s = sample(wide, features, base, end)
            if s is not None:
                rows.append(s)
    return pd.concat(rows).reset_index()


def window_dataset(wide: pd.DataFrame, features: dict, origin, cache=None) -> pd.DataFrame:
    """Samples of the non-overlapping four-week windows ending on or before ``origin``.

    ``cache`` (a dict) reuses the windows shared by consecutive origins.
    """
    cache = {} if cache is None else cache
    rows = []
    for window in past_windows(wide.index, origin, None):
        if window not in cache:
            cache[window] = sample(wide, features, *window)
        if cache[window] is not None:
            rows.append(cache[window])
    return pd.concat(rows).reset_index()


def expand(data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = data[RANK_COLUMNS].to_numpy(dtype=float)
    rows, labels = np.nonzero(t > 0)
    return data[FEATURES].to_numpy(dtype=float)[rows], labels, t[rows, labels]


def fit_predict(train: pd.DataFrame, x_test: np.ndarray, config: dict, seed: int, threads: int):
    """Train at the largest number of rounds; predictions at every value of ``ROUNDS``."""
    x, y, w = expand(train)
    params = {**FIXED_PARAMS, **config, "seed": seed, "num_threads": threads}
    booster = lgb.train(params, lgb.Dataset(x, y, weight=w), num_boost_round=max(ROUNDS))
    return {r: booster.predict(x_test, num_iteration=r) for r in ROUNDS}


def _frame(values: np.ndarray, symbols) -> pd.DataFrame:
    probs = pd.DataFrame(values, index=list(symbols), columns=RANK_COLUMNS)
    return probs.div(probs.sum(axis=1), axis=0)


def kfold_forecasts(data: pd.DataFrame, origins, grid=None, k=5, seed=2026, threads=4) -> dict:
    """s0: out-of-fold predictions with rows shuffled over the whole sample."""
    rng = np.random.default_rng(seed)
    fold = rng.permutation(len(data)) % k
    is_origin = data["base"].isin(list(origins)).to_numpy()
    out = {}
    for i, config in enumerate(configs(grid)):
        preds = {r: np.full((len(data), 5), np.nan) for r in ROUNDS}
        for f in range(k):
            test = (fold == f) & is_origin
            if not test.any():
                continue
            x_test = data.loc[test, FEATURES].to_numpy(dtype=float)
            for r, p in fit_predict(data[fold != f], x_test, config, seed, threads).items():
                preds[r][test] = p
        for r in ROUNDS:
            out[(i, r)] = {}
            for o in origins:
                rows = (data["base"] == o).to_numpy()
                out[(i, r)][o] = _frame(preds[r][rows], data.loc[rows, "symbol"])
    return out


def walk_forward_forecasts(train_for, test_for, origins, grid=None, seed=2026, threads=4) -> dict:
    """s1-s3: one model per origin and configuration.

    ``train_for(origin)`` and ``test_for(origin)`` return the training rows and the rows
    to predict (features of every asset at the origin).
    """
    out = {(i, r): {} for i in range(len(configs(grid))) for r in ROUNDS}
    for origin in origins:
        train, test = train_for(origin), test_for(origin)
        x_test = test[FEATURES].to_numpy(dtype=float)
        for i, config in enumerate(configs(grid)):
            for r, p in fit_predict(train, x_test, config, seed, threads).items():
                out[(i, r)][origin] = _frame(p, test["symbol"])
    return out


def origin_rows(features: dict, origin, symbols: list[str]) -> pd.DataFrame:
    x = pd.DataFrame({name: features[name].loc[origin, symbols] for name in FEATURES})
    return x.rename_axis("symbol").reset_index()


def select_ex_post(candidates: dict, score) -> tuple[tuple, pd.DataFrame]:
    """The candidate with the best mean RPS on the evaluation periods (the bias of
    selecting and reporting on the same data), and the score of every candidate."""
    table = pd.DataFrame(
        [{"config": c, "rounds": r, "rps": score(f)} for (c, r), f in candidates.items()]
    )
    best = table.loc[table["rps"].idxmin()]
    return (int(best["config"]), int(best["rounds"])), table


def annualized_sharpe(log_returns: pd.Series, days: int = 252) -> float:
    sd = log_returns.std(ddof=1)
    return float(log_returns.mean() / sd * np.sqrt(days)) if sd > 0 else float("nan")


__all__ = [
    "ROUNDS",
    "SUCCESSORS",
    "annualized_sharpe",
    "configs",
    "cross_sectional_features",
    "expand",
    "fit_predict",
    "forward_end",
    "kfold_forecasts",
    "naive_features",
    "origin_rows",
    "sample",
    "select_ex_post",
    "survivors_universe",
    "to_wide",
    "walk_forward_forecasts",
    "weekly_dataset",
    "window_dataset",
]
