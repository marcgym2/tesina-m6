"""Quintile probabilities by simulation from an estimated covariance matrix (issue #22).

At each forecast origin:

1. Covariance. An exponentially weighted (RiskMetrics-style, zero-mean) covariance of
   daily log returns, estimated with prices dated on or before the origin (rule 2).
   Pairs are estimated on their common observations; the matrix is made positive
   semi-definite by clipping negative eigenvalues. An asset with fewer than
   ``min_obs`` returns gets the median variance of the others and zero covariances.
2. Simulation. ``n_sims`` joint Gaussian scenarios of the next period's returns with
   mean zero. Each scenario ranks the assets cross-sectionally (rule 3) and maps ranks
   to quintiles with the proportional thresholds; probabilities are the frequencies.
   Fixed seed and common random numbers make forecasts reproducible.

Why mean zero and Gaussian. No expected-return forecast is attempted: the model only
encodes that volatile assets are more likely to land in the extreme quintiles and that
correlated assets move together. With mean zero the quintile probabilities do not
depend on the horizon (scaling the covariance does not change ranks), and any
elliptical distribution with a common mixing variable (e.g. a multivariate t) gives
the same rank distribution as the Gaussian, so the Gaussian loses nothing.

Hyper-parameter (rule 2). The half-life of the weights is chosen at each origin from a
fixed grid by the mean RPS over the last ``n_val`` past four-week windows: for each
window the forecast uses only prices up to the window's base date and is scored on the
window's realised quintiles; every window ends on or before the origin (rules 1 and 4).
Every candidate at every origin is kept in ``search_log``.

Weights. Equal weights (the M6 investment benchmark). A tilt towards the expected
quintile is meaningless here: with mean zero every asset's expected quintile is 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.baselines import equal_weights, past_windows


def ewma_covariance(daily: pd.DataFrame, halflife: float, min_obs: int = 20) -> np.ndarray:
    """Zero-mean EWMA covariance of the rows of ``daily`` (NaN = no observation).

    Uses the last ``5 * halflife`` rows; the most recent row has the largest weight.
    """
    window = daily.iloc[-int(np.ceil(5 * halflife)) :]
    r = window.to_numpy(dtype=float)
    observed = np.isfinite(r)
    r = np.where(observed, r, 0.0)
    m = observed.astype(float)
    age = np.arange(len(r))[::-1]
    w = 0.5 ** (age / halflife)
    num = (r * w[:, None]).T @ r
    den = (m * w[:, None]).T @ m
    cov = np.divide(num, den, out=np.zeros_like(num), where=den > 0)

    n_obs = m.sum(axis=0)
    short = n_obs < min_obs
    if short.any():
        fill = np.median(np.diag(cov)[~short]) if (~short).any() else 1e-4
        cov[short, :] = 0.0
        cov[:, short] = 0.0
        cov[short, short] = fill
    values, vectors = np.linalg.eigh((cov + cov.T) / 2)
    return (vectors * np.clip(values, 0, None)) @ vectors.T


def simulate_quintile_probs(cov: np.ndarray, n_sims: int, seed: int) -> np.ndarray:
    """Quintile probabilities (n x 5) of zero-mean Gaussian returns with covariance ``cov``."""
    n = len(cov)
    values, vectors = np.linalg.eigh(cov)
    root = vectors * np.sqrt(np.clip(values, 0, None))
    z = np.random.default_rng(seed).standard_normal((n_sims, n))
    return quintile_frequencies(z @ root.T)


def quintile_frequencies(sims: np.ndarray) -> np.ndarray:
    """Quintile probabilities (n x 5) from scenarios (n_sims x n) of the assets' returns.

    Each scenario ranks the assets and maps ranks to quintiles with the proportional
    thresholds (k * n / 5); probabilities are the frequencies over scenarios.
    """
    n_sims, n = sims.shape
    position = sims.argsort(axis=1).argsort(axis=1) + 1  # 1 = lowest return
    thresholds = np.array([k * n / 5 for k in range(1, 5)])
    quintile = np.searchsorted(thresholds, position, side="left")  # 0..4
    counts = np.stack([(quintile == q).sum(axis=0) for q in range(5)], axis=1)
    return counts / n_sims


@dataclass
class CovarianceSimulation:
    halflives: tuple = (21, 63, 126, 252)  # trading days
    n_val: int = 12  # past windows used to choose the half-life
    n_sims: int = 10_000
    min_obs: int = 20
    seed: int = 2026
    name: str = "covsim"
    search_log: list = field(default_factory=list, repr=False)

    def _probs(self, daily: pd.DataFrame, symbols, halflife) -> pd.DataFrame:
        cov = ewma_covariance(daily[symbols], halflife, self.min_obs)
        probs = simulate_quintile_probs(cov, self.n_sims, self.seed)
        return pd.DataFrame(probs, index=symbols, columns=RANK_COLUMNS)

    def forecast(self, history, universe, origin) -> Forecast:
        origin = pd.Timestamp(origin)
        history = history[(history["symbol"].isin(universe)) & (history["date"] <= origin)]
        wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        wide = wide.sort_index().ffill().reindex(columns=universe)
        daily = np.log(wide).diff()
        halflife = self._select(wide, daily, origin)
        probs = self._probs(daily, universe, halflife)
        return Forecast(probs, equal_weights(universe))

    def _select(self, wide, daily, origin) -> float:
        windows = list(reversed(past_windows(wide.index, origin, self.n_val)))
        scored = []
        for base, end in windows:
            returns = period_returns(wide.loc[base:end]).dropna()
            if len(returns) < 5:
                continue
            targets = quintile_targets(returns, "proportional")
            scored.append((daily.loc[:base], list(returns.index), targets))
        if not scored:
            default = self.halflives[len(self.halflives) // 2]
            self.search_log.append({"origin": origin, "fallback": True, "halflife": default})
            return default
        entries = []
        for halflife in self.halflives:
            scores = [
                float(rps_per_asset(self._probs(d, symbols, halflife), targets).mean())
                for d, symbols, targets in scored
            ]
            entries.append(
                {
                    "origin": origin,
                    "fallback": False,
                    "n_val_windows": len(scored),
                    "val_start": windows[0][0],
                    "val_end": windows[-1][1],
                    "halflife": halflife,
                    "val_rps": float(np.mean(scores)),
                    "chosen": False,
                }
            )
        best = min(entries, key=lambda e: e["val_rps"])
        best["chosen"] = True
        self.search_log.extend(entries)
        return best["halflife"]
