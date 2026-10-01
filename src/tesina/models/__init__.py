"""Forecasting models: the interface every model implements and its validation.

A model receives only the prices available at the forecast origin (the walk-forward
harness enforces it) and returns, for the next four-week period, quintile
probabilities and investment weights for every asset of the universe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

RANK_COLUMNS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]

# M6 submission rules (Makridakis et al., arXiv:2310.13357v1, section 2): a sum of
# absolute weights above 1 or below 0.25 makes a submission invalid; any remainder
# below 1 is held in an asset with zero return and zero risk.
MIN_GROSS_EXPOSURE = 0.25
MAX_GROSS_EXPOSURE = 1.0


@dataclass(frozen=True)
class Forecast:
    probs: pd.DataFrame  # index: symbol; columns: Rank1..Rank5
    weights: pd.Series  # index: symbol


class Model(Protocol):
    name: str

    def forecast(
        self, history: pd.DataFrame, universe: list[str], origin: pd.Timestamp
    ) -> Forecast:
        """Forecast the period that starts after the close of ``origin``.

        ``history`` contains prices (``symbol``, ``date``, ``price``) up to ``origin``.
        """
        ...


def validate_forecast(forecast: Forecast, universe: list[str], tol: float = 1e-6) -> None:
    """Raise ``ValueError`` if the forecast breaks the M6 submission rules."""
    probs, weights = forecast.probs, forecast.weights
    if set(probs.index) != set(universe) or list(probs.columns) != RANK_COLUMNS:
        raise ValueError("probs must have one row per universe asset and columns Rank1..Rank5")
    values = probs.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < -tol).any():
        raise ValueError("probabilities must be finite and non-negative")
    if np.abs(values.sum(axis=1) - 1).max() > tol:
        raise ValueError("probabilities of each asset must sum to 1")
    if set(weights.index) != set(universe):
        raise ValueError("weights must have one entry per universe asset")
    if not np.isfinite(weights.to_numpy(dtype=float)).all():
        raise ValueError("weights must be finite")
    gross = float(weights.abs().sum())
    if not MIN_GROSS_EXPOSURE - tol <= gross <= MAX_GROSS_EXPOSURE + tol:
        raise ValueError(f"sum of absolute weights {gross:.4f} outside [0.25, 1]")
