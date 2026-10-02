"""AdaGaussMC: reimplementation from the paper (issue #20).

de Vilmarest and Werge, "An adaptive volatility method for probabilistic forecasting
and its application to the M6 financial forecasting competition", arXiv:2303.01855v2
(sections 2 and 4). The team's own pipeline is not public; only AdaVol, the volatility
model it uses, is (vendored in ``vendor/adagaussmc``). Fidelity notes are in
``vendor/adagaussmc/NOTICE.md``.

At each forecast origin:

1. **Class means.** Assets belong to the paper's classes (Table 1): stocks, ETF
   equities, ETF fixed income, ETF commodities, and the volatility ETF (VXX). The
   expected daily log return of an asset is the mean daily log return of all assets of
   its class over ``class_window`` (2015-2020 in the paper), fixed thereafter.
2. **Volatility.** AdaVol (GARCH(1,1), online QML with projected AdaGrad, eta = 0.1,
   initial (alpha, beta) = (0.05, 0.90)) runs over each asset's daily log returns minus
   its class mean, from ``vol_start`` to the origin; its one-step-ahead variance is held
   fixed over the horizon (section 4.1).
3. **Distribution of the period.** Daily log returns are independent N(mu, sigma^2),
   so the period's log return is N(h mu, h sigma^2) with h = 20 trading days. VXX
   instead sums h draws from the empirical distribution of its past daily log returns.
   Assets are independent for the forecasting task (section 4.1).
4. **Probabilities.** The paper minimises the expected RPS under that distribution
   with ADAM. The RPS is a quadratic loss between linear transforms of the forecast and
   of the outcome (section 2), so the minimiser is the expected outcome: the quintile
   frequencies, computed here directly by Monte Carlo. Ranks are cross-sectional in each
   scenario (rule 3 of CLAUDE.md).

Weights: the paper's investment step (correlated Gaussian returns and ADAM on the
expected information ratio) does not specify the correlation estimator nor the
optimiser settings, so it is not reproduced; the weights are the M6 benchmark (1/n),
as for the other forecast-only methods.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd

from tesina.data import m6
from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.baselines import equal_weights
from tesina.models.covsim import quintile_frequencies

# Paper, Table 1 (asset IDs of the M6 universe file): stocks 1-50, ETF equities 51-67
# and 80-99, ETF fixed income 68-76, ETF commodities 77-79, volatility 100.
FIXED_INCOME = ["LQD", "HYG", "SHY", "IEF", "TLT", "SEGA.L", "IEAA.L", "HIGH.L", "JPEA.L"]
COMMODITIES = ["IAU", "SLV", "GSG"]
VOLATILITY = ["VXX"]
ETF_EQUITIES = [
    "IVV", "IWM", "EWU", "EWG", "EWL", "EWQ", "IEUS", "EWJ", "EWT", "MCHI", "INDA", "EWY",
    "EWA", "EWH", "EWZ", "EWC", "IEMG", "REET", "ICLN", "IXN", "IGF", "IUVL.L", "IUMO.L",
    "SPMV.L", "IEVL.L", "IEFM.L", "MVEU.L", "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XLC",
    "XLU", "XLP", "XLB",
]  # fmt: skip


def asset_class(symbol: str) -> str:
    if symbol in FIXED_INCOME:
        return "etf_fixed_income"
    if symbol in COMMODITIES:
        return "etf_commodities"
    if symbol in VOLATILITY:
        return "etf_volatility"
    if symbol in ETF_EQUITIES:
        return "etf_equities"
    return "stock"


@cache
def adavol_module():
    """The AdaVol port in vendor/adagaussmc (GPL-3.0, kept outside the package)."""
    path = m6.REPO_ROOT / "vendor" / "adagaussmc" / "adavol.py"
    spec = importlib.util.spec_from_file_location("adavol", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adavol_forecast(x: np.ndarray, theta0=(0.05, 0.90), eta: float = 0.1) -> float:
    """One-step-ahead variance of AdaVol after the last observation of ``x``."""
    x = np.asarray(x, dtype=float)
    _, sigma2 = adavol_module().adavol(x, np.array(theta0), p=1, q=1, eta=eta)
    return sigma2


@dataclass
class AdaGaussMC:
    class_window: tuple = ("2015-01-01", "2020-12-31")
    vol_start: str = "2015-01-01"
    horizon: int = 20  # trading days in a four-week period
    min_obs: int = 20  # fewer returns: the class's median variance is used
    theta0: tuple = (0.05, 0.90)
    eta: float = 0.1
    n_sims: int = 20_000
    seed: int = 2026
    name: str = "adagaussmc"
    log: list = field(default_factory=list, repr=False)

    def class_means(self, daily: pd.DataFrame) -> dict[str, float]:
        start, end = (pd.Timestamp(d) for d in self.class_window)
        window = daily.loc[start:end]
        means = {}
        for cls in ("stock", "etf_equities", "etf_fixed_income", "etf_commodities"):
            cols = [s for s in window.columns if asset_class(s) == cls]
            values = window[cols].to_numpy().ravel() if cols else np.array([])
            values = values[np.isfinite(values)]
            means[cls] = float(values.mean()) if len(values) else 0.0
        return means

    def forecast(self, history, universe, origin) -> Forecast:
        origin = pd.Timestamp(origin)
        history = history[(history["symbol"].isin(universe)) & (history["date"] <= origin)]
        wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        wide = wide.sort_index().ffill().reindex(columns=universe)
        daily = np.log(wide).diff()
        means = self.class_means(daily)
        recent = daily.loc[pd.Timestamp(self.vol_start) :]

        mu, sigma2 = {}, {}
        for symbol in universe:
            cls = asset_class(symbol)
            if cls == "etf_volatility":
                continue
            x = recent[symbol].dropna().to_numpy()
            mu[symbol] = means[cls]
            if len(x) >= self.min_obs:
                sigma2[symbol] = adavol_forecast(x - means[cls], self.theta0, self.eta)
        for symbol in mu:
            if symbol not in sigma2:  # short history: median variance of its class
                peers = [v for s, v in sigma2.items() if asset_class(s) == asset_class(symbol)]
                sigma2[symbol] = (
                    float(np.median(peers)) if peers else float(np.median(list(sigma2.values())))
                )
        self.log.append({"origin": origin, "class_means": means, "n_vol": len(sigma2)})

        rng = np.random.default_rng(self.seed)
        sims = np.empty((self.n_sims, len(universe)))
        for j, symbol in enumerate(universe):
            past = recent[symbol].dropna().to_numpy()
            if asset_class(symbol) == "etf_volatility" and len(past) >= self.min_obs:
                draws = rng.choice(past, size=(self.n_sims, self.horizon), replace=True)
                sims[:, j] = draws.sum(axis=1)
            elif asset_class(symbol) == "etf_volatility":  # no history yet: widest variance
                scale = np.sqrt(self.horizon * max(sigma2.values()))
                sims[:, j] = rng.normal(0.0, scale, self.n_sims)
            else:
                h = self.horizon
                sims[:, j] = rng.normal(h * mu[symbol], np.sqrt(h * sigma2[symbol]), self.n_sims)
        probs = pd.DataFrame(quintile_frequencies(sims), index=universe, columns=RANK_COLUMNS)
        return Forecast(probs, equal_weights(universe))
