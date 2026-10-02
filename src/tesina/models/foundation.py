"""Zero-shot foundation model: TimesFM-3 (issue #23, decision D7).

At each forecast origin, for every asset of the universe:

1. Context: the last ``context`` daily log prices up to the origin (rule 2). The
   pretrained model is used as is: no fine-tuning and no hyper-parameter search.
2. Marginal forecast: TimesFM-3 returns the deciles (0.1, ..., 0.9) of the log price
   ``horizon`` trading days ahead (20 = four weeks); minus the log price at the origin
   they are deciles of the asset's log return over the period. The quantile function
   is linear between deciles and continues below 0.1 and above 0.9 with Gaussian tails
   whose scale matches the outermost decile gap.
3. Joint scenarios: TimesFM-3 forecasts each asset on its own and gives no joint
   samples, so assets are tied by a Gaussian copula whose correlation comes from the
   EWMA covariance of daily log returns up to the origin (``ewma_covariance`` of the
   covariance model, #22, with a fixed half-life). Each of ``n_sims`` scenarios ranks
   the assets cross-sectionally (rule 3); quintile probabilities are the frequencies.

The model weights are not part of the repository (non-commercial licence, see
``docs/timesfm.md``); the checkpoint is pinned to a Hugging Face revision. What the
model saw during pre-training, and the contamination risk for periods 1 and 2, is
documented in ``docs/timesfm.md``.

Weights. ``"equal"`` (the M6 benchmark) or ``"expected_rank"`` (as in the GBM, #21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd
from scipy.stats import norm

from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.covsim import ewma_covariance, quintile_frequencies
from tesina.models.weighting import weights_for

CHECKPOINT = "google/timesfm-3.0-pytorch"
REVISION = "43046b85ec22d584a13f8098c2ed39c889e129c2"  # Hugging Face commit of the weights
DECILES = np.linspace(0.1, 0.9, 9)


class QuantileForecaster(Protocol):
    def __call__(self, contexts: list[np.ndarray], horizon: int) -> np.ndarray:
        """Deciles of each series at each step ahead, shape (n_series, horizon, 9)."""
        ...


@dataclass
class TimesFM3Backend:
    """TimesFM-3 through its MLX backend (Apple silicon); loaded on first use."""

    checkpoint: str = CHECKPOINT
    revision: str = REVISION
    batch_size: int = 32
    _forecaster: object = field(default=None, init=False, repr=False)

    def __call__(self, contexts, horizon) -> np.ndarray:
        if self._forecaster is None:
            from timesfm3.mlx import TimesFM3Forecaster  # optional extra "timesfm"

            self._forecaster = TimesFM3Forecaster.from_pretrained(
                self.checkpoint, revision=self.revision
            )
        out = []
        for start in range(0, len(contexts), self.batch_size):
            batch = contexts[start : start + self.batch_size]
            outputs = self._forecaster.predict_batch(batch, horizon=horizon, return_quantiles=True)
            out.extend(np.asarray(o.quantiles, dtype=float) for o in outputs)
        return np.stack(out)


def quantile_function(deciles: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Evaluate, column by column, quantile functions given by their deciles.

    ``deciles`` is (n, 9) and ``u`` is (n_sims, n) in (0, 1). Linear between deciles;
    Gaussian tails beyond 0.1 and 0.9 with the scale of the outermost decile gap.
    """
    z = norm.ppf(DECILES)
    out = np.empty_like(u, dtype=float)
    for i in range(deciles.shape[0]):
        q = np.maximum.accumulate(deciles[i])
        out[:, i] = np.interp(u[:, i], DECILES, q)
        low, high = u[:, i] < DECILES[0], u[:, i] > DECILES[-1]
        scale_low = (q[1] - q[0]) / (z[1] - z[0])
        scale_high = (q[-1] - q[-2]) / (z[-1] - z[-2])
        out[low, i] = q[0] + scale_low * (norm.ppf(u[low, i]) - z[0])
        out[high, i] = q[-1] + scale_high * (norm.ppf(u[high, i]) - z[-1])
    return out


def correlation(cov: np.ndarray) -> np.ndarray:
    sd = np.sqrt(np.diag(cov))
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = cov / np.outer(sd, sd)
    corr = np.where(np.isfinite(corr), corr, 0.0)
    np.fill_diagonal(corr, 1.0)
    return corr


@dataclass
class TimesFM:
    backend: QuantileForecaster | None = None  # None: TimesFM3Backend()
    context: int = 1024  # trading days of log prices given to the model
    horizon: int = 20  # trading days in a four-week period
    min_context: int = 32  # shorter series take the cross-sectional median deciles
    copula_halflife: float = 126  # trading days; fixed, not tuned
    n_sims: int = 10_000
    seed: int = 2026
    weighting: str = "equal"  # "equal" (M6 benchmark) or "expected_rank"
    name: str = "timesfm3"
    deciles_log: dict = field(default_factory=dict, repr=False)  # origin -> deciles

    def __post_init__(self):
        if self.backend is None:
            self.backend = TimesFM3Backend()

    def return_deciles(self, logp: pd.DataFrame) -> pd.DataFrame:
        """Deciles (symbol x 9) of each asset's log return over the next period."""
        symbols = list(logp.columns)
        contexts = {s: logp[s].dropna().to_numpy()[-self.context :] for s in symbols}
        usable = [s for s in symbols if len(contexts[s]) >= self.min_context]
        deciles = pd.DataFrame(np.nan, index=symbols, columns=DECILES)
        if usable:
            batch = [contexts[s].astype(np.float32) for s in usable]
            quantiles = np.asarray(self.backend(batch, self.horizon), dtype=float)
            if quantiles.shape != (len(usable), self.horizon, 9):
                raise ValueError(f"backend returned shape {quantiles.shape}")
            last = np.array([contexts[s][-1] for s in usable])
            deciles.loc[usable] = quantiles[:, -1, :] - last[:, None]
        fill = deciles.median() if usable else pd.Series(0.0, index=DECILES)
        return deciles.fillna(fill)

    def forecast(self, history, universe, origin) -> Forecast:
        origin = pd.Timestamp(origin)
        history = history[(history["symbol"].isin(universe)) & (history["date"] <= origin)]
        wide = history.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        logp = np.log(wide.sort_index().ffill().reindex(columns=universe))
        deciles = self.return_deciles(logp)
        self.deciles_log[origin] = deciles

        corr = correlation(ewma_covariance(logp.diff(), self.copula_halflife))
        values, vectors = np.linalg.eigh(corr)
        root = vectors * np.sqrt(np.clip(values, 0, None))
        z = np.random.default_rng(self.seed).standard_normal((self.n_sims, len(universe)))
        u = norm.cdf(z @ root.T).clip(1e-12, 1 - 1e-12)
        sims = quantile_function(deciles.to_numpy(), u)
        probs = pd.DataFrame(quintile_frequencies(sims), index=universe, columns=RANK_COLUMNS)

        weights = weights_for(probs, self.weighting)
        return Forecast(probs, weights)
