"""Multiclass gradient boosting on price features (issue #21).

At each forecast origin the model is trained from scratch with LightGBM on past
four-week windows and predicts the quintile probabilities of the next period.

Samples. One sample per (window, asset): features measured at the window's base date,
label = the asset's quintile over the window, computed cross-sectionally among the
universe members priced in that window (rule 3 of CLAUDE.md, ``"proportional"``
thresholds because past cross-sections may have fewer than 100 assets). Windows are
those of ``past_windows``: they step back 28 days from the origin, so labels never
overlap each other and the most recent one ends at the origin (rules 1 and 4). Ties in
a quintile target become several rows weighted by their share.

Features. Causal statistics of each asset's price path (log returns over 1, 4, 12 and
24 weeks, 12-1 month momentum, 4- and 12-week daily volatility, their ratio and the
distance to the 52-week high), each converted to its cross-sectional percentile rank
on the same date. Ranking within a date needs no scaler fitted across time (rule 2).

Hyper-parameters (rule 2). The last ``n_val`` windows are a validation block; the
model is trained on the windows before it, leaving ``embargo`` windows in between, for
every configuration of a fixed grid, with early stopping on the validation RPS. The
configuration with the lowest validation RPS is refitted on all windows with its
number of boosting rounds. Every configuration tried at every origin is kept in
``search_log`` so the full search can be reported.

Weights. ``"equal"`` holds the M6 investment benchmark (1/n), so that the model only
differs from the baselines in its forecasts; ``"expected_rank"`` tilts towards the
expected quintile: w_i ∝ E[quintile_i] - 3, scaled to a gross exposure of ``gross``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

import lightgbm as lgb
import numpy as np
import pandas as pd

from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.baselines import equal_weights, past_windows

FEATURES = [
    "ret_5",
    "ret_20",
    "ret_60",
    "ret_120",
    "mom_250_20",
    "vol_20",
    "vol_60",
    "vol_ratio",
    "dist_high_250",
]

DEFAULT_GRID = {"num_leaves": [7, 31], "min_data_in_leaf": [100, 500]}

FIXED_PARAMS = {
    "objective": "multiclass",
    "num_class": 5,
    "metric": "None",
    "learning_rate": 0.03,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "deterministic": True,
    "force_row_wise": True,
    "verbosity": -1,
}


def price_signals(wide: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-asset signals (date x symbol); row t only uses prices dated on or before t."""
    logp = np.log(wide)
    daily = logp.diff()
    vol_20 = daily.rolling(20).std()
    vol_60 = daily.rolling(60).std()
    return {
        "ret_5": logp.diff(5),
        "ret_20": logp.diff(20),
        "ret_60": logp.diff(60),
        "ret_120": logp.diff(120),
        "mom_250_20": logp.shift(20) - logp.shift(250),
        "vol_20": vol_20,
        "vol_60": vol_60,
        "vol_ratio": vol_20 / vol_60,
        "dist_high_250": logp - logp.rolling(250, min_periods=60).max(),
    }


def cross_sectional_features(wide: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Each signal as its percentile rank among the assets with a value on that date."""
    return {name: s.rank(axis=1, pct=True) for name, s in price_signals(wide).items()}


def features_at(features: dict[str, pd.DataFrame], date, symbols) -> pd.DataFrame:
    """Feature matrix (symbol x feature) on ``date``."""
    return pd.DataFrame({name: features[name].loc[date, symbols] for name in FEATURES})


def training_windows(wide: pd.DataFrame, features, origin, lookback=None, min_assets=5):
    """Samples of the past windows, oldest first: a list of ``(base, end, X, targets)``."""
    windows = []
    for base, end in reversed(past_windows(wide.index, origin, lookback)):
        returns = period_returns(wide.loc[base:end]).dropna()
        if len(returns) < min_assets:
            continue
        targets = quintile_targets(returns, "proportional")
        windows.append((base, end, features_at(features, base, returns.index), targets))
    return windows


def split_windows(n_windows: int, n_val: int, embargo: int) -> tuple[list[int], list[int]]:
    """Indices (chronological) of the training and validation windows."""
    val = list(range(n_windows - n_val, n_windows))
    train = list(range(0, max(n_windows - n_val - embargo, 0)))
    return train, val


def _expand(windows) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stack windows into (X, label, weight); tied targets become weighted rows."""
    xs, ys, ws = [], [], []
    for _, _, x, targets in windows:
        t = targets.to_numpy(dtype=float)
        rows, labels = np.nonzero(t > 0)
        xs.append(x.to_numpy(dtype=float)[rows])
        ys.append(labels)
        ws.append(t[rows, labels])
    return np.vstack(xs), np.concatenate(ys), np.concatenate(ws)


def _rps_eval(preds, data):
    """LightGBM metric: weighted mean RPS of one-hot labels (lower is better)."""
    y = data.get_label().astype(int)
    w = data.get_weight()
    cum_f = np.cumsum(preds.reshape(len(y), 5), axis=1)
    cum_t = (np.arange(5)[None, :] >= y[:, None]).astype(float)
    per_row = ((cum_t - cum_f) ** 2).mean(axis=1)
    return "rps", float(np.average(per_row, weights=w)), False


def window_rps(booster: lgb.Booster, windows, num_iteration=None) -> float:
    """Mean over windows of the official per-period RPS."""
    scores = []
    for _, _, x, targets in windows:
        probs = pd.DataFrame(
            booster.predict(x.to_numpy(dtype=float), num_iteration=num_iteration),
            index=x.index,
            columns=RANK_COLUMNS,
        )
        scores.append(float(rps_per_asset(probs, targets).mean()))
    return float(np.mean(scores))


def expected_rank_weights(probs: pd.DataFrame, gross: float = 1.0) -> pd.Series:
    score = probs[RANK_COLUMNS].to_numpy(dtype=float) @ np.arange(1, 6) - 3
    total = np.abs(score).sum()
    if total == 0:
        return equal_weights(list(probs.index)) * gross
    return pd.Series(gross * score / total, index=probs.index)


@dataclass
class GBM:
    grid: dict = field(default_factory=lambda: dict(DEFAULT_GRID))
    n_val: int = 12  # validation windows (about one year)
    embargo: int = 1  # windows dropped between training and validation
    min_train_windows: int = 24  # below this, forecast uniform (logged as a fallback)
    lookback: int | None = None  # number of past windows; None = expanding
    max_rounds: int = 1000
    early_stopping: int = 50
    weighting: str = "equal"  # "equal" (M6 benchmark) or "expected_rank"
    gross: float = 1.0
    seed: int = 2026
    num_threads: int = 1
    name: str = "gbm"
    search_log: list = field(default_factory=list, repr=False)

    def _params(self, config: dict) -> dict:
        return {**FIXED_PARAMS, **config, "seed": self.seed, "num_threads": self.num_threads}

    def _configs(self) -> list[dict]:
        keys = sorted(self.grid)
        grid = product(*(self.grid[k] for k in keys))
        return [dict(zip(keys, values, strict=True)) for values in grid]

    def forecast(self, history, universe, origin) -> Forecast:
        origin = pd.Timestamp(origin)
        history = history[(history["symbol"].isin(universe)) & (history["date"] <= origin)]
        wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        wide = wide.sort_index().ffill().reindex(columns=universe)
        features = cross_sectional_features(wide)
        windows = training_windows(wide, features, origin, self.lookback)
        train_idx, val_idx = split_windows(len(windows), self.n_val, self.embargo)

        if len(train_idx) < self.min_train_windows:
            self.search_log.append({"origin": origin, "fallback": True, "n_windows": len(windows)})
            probs = pd.DataFrame(0.2, index=universe, columns=RANK_COLUMNS)
        else:
            config, rounds = self._select(windows, train_idx, val_idx, origin)
            x, y, w = _expand(windows)
            booster = lgb.train(
                self._params(config), lgb.Dataset(x, y, weight=w), num_boost_round=rounds
            )
            x0 = features_at(features, wide.index[-1], universe)
            probs = pd.DataFrame(
                booster.predict(x0.to_numpy(dtype=float)), index=universe, columns=RANK_COLUMNS
            )
            probs = probs.div(probs.sum(axis=1), axis=0)
        if self.weighting == "equal":
            weights = equal_weights(universe)
        elif self.weighting == "expected_rank":
            weights = expected_rank_weights(probs, self.gross)
        else:
            raise ValueError(f"unknown weighting {self.weighting!r}")
        return Forecast(probs, weights)

    def _select(self, windows, train_idx, val_idx, origin) -> tuple[dict, int]:
        train = [windows[i] for i in train_idx]
        val = [windows[i] for i in val_idx]
        x_tr, y_tr, w_tr = _expand(train)
        x_va, y_va, w_va = _expand(val)
        best = None
        for config in self._configs():
            dtrain = lgb.Dataset(x_tr, y_tr, weight=w_tr)
            dval = lgb.Dataset(x_va, y_va, weight=w_va, reference=dtrain)
            booster = lgb.train(
                self._params(config),
                dtrain,
                num_boost_round=self.max_rounds,
                valid_sets=[dval],
                feval=_rps_eval,
                callbacks=[lgb.early_stopping(self.early_stopping, verbose=False)],
            )
            rounds = max(booster.best_iteration, 1)
            score = window_rps(booster, val, num_iteration=rounds)
            entry = {
                "origin": origin,
                "fallback": False,
                "n_windows": len(windows),
                "train_start": train[0][0],
                "train_end": train[-1][1],
                "val_start": val[0][0],
                "val_end": val[-1][1],
                **config,
                "rounds": rounds,
                "val_rps": score,
                "chosen": False,
            }
            self.search_log.append(entry)
            if best is None or score < best[0]["val_rps"]:
                best = (entry, config, rounds)
        best[0]["chosen"] = True
        return best[1], best[2]
