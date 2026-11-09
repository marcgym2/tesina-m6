"""How close a re-run method is to what its team actually submitted in period 1."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.models import RANK_COLUMNS


def compare_with_submissions(result, prices: pd.DataFrame, subs: pd.DataFrame) -> pd.DataFrame:
    """One row per period of a walk-forward ``result`` (official 100-asset universe).

    ``subs`` holds one team's submissions (``Evaluation``, ``Symbol``, ``Rank1``..``Rank5``).
    Reports the correlation of ``p - 0.2`` between re-run and submission, their absolute
    differences, and the RPS of both on the period's realised quintiles.
    """
    rows = []
    for period in result.periods.itertuples():
        repro = result.forecasts[period.label].probs
        actual = subs[subs["Evaluation"] == period.label].set_index("Symbol")[RANK_COLUMNS]
        actual = actual.astype(float).loc[repro.index]
        wide = period_prices(prices, period.origin, period.end_date)[repro.index]
        targets = quintile_targets(period_returns(wide))
        x, y = (repro - 0.2).to_numpy().ravel(), (actual - 0.2).to_numpy().ravel()
        rows.append(
            {
                "k": period.k,
                "label": period.label,
                "corr": float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else np.nan,
                "mean_abs_diff": float(np.abs(x - y).mean()),
                "max_abs_diff": float(np.abs(x - y).max()),
                "rps_submission": float(rps_per_asset(actual, targets).mean()),
                "rps_reproduction": float(rps_per_asset(repro, targets).mean()),
            }
        )
    return pd.DataFrame(rows)
