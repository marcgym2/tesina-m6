"""Rules that turn quintile probabilities into M6 investment weights.

- ``"equal"``: the M6 investment benchmark (1/n), so a model differs from the
  baselines only in its forecasts.
- ``"expected_rank"``: w_i ∝ E[quintile_i] - 3, scaled to a gross exposure ``gross``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.baselines import equal_weights

WEIGHTINGS = ("equal", "expected_rank")


def expected_rank_weights(probs: pd.DataFrame, gross: float = 1.0) -> pd.Series:
    score = probs[RANK_COLUMNS].to_numpy(dtype=float) @ np.arange(1, 6) - 3
    total = np.abs(score).sum()
    if total == 0:
        return equal_weights(list(probs.index)) * gross
    return pd.Series(gross * score / total, index=probs.index)


def weights_for(probs: pd.DataFrame, weighting: str, gross: float = 1.0) -> pd.Series:
    if weighting == "equal":
        return equal_weights(list(probs.index))
    if weighting == "expected_rank":
        return expected_rank_weights(probs, gross)
    raise ValueError(f"unknown weighting {weighting!r}")


@dataclass
class Reweighted:
    """Replays fitted probabilities (by origin) with a given weighting rule.

    Experiments fit a model once and evaluate every weighting on the same forecasts,
    so a hyper-parameter search is neither repeated nor double-counted.
    """

    probs: dict[pd.Timestamp, pd.DataFrame]
    weighting: str
    name: str

    def forecast(self, history, universe, origin) -> Forecast:
        probs = self.probs[pd.Timestamp(origin)]
        return Forecast(probs, weights_for(probs, self.weighting))
