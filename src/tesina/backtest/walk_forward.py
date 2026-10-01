"""Walk-forward evaluation harness (issue #15).

For every period of a resolved calendar (``tesina.evaluation.calendar.resolve``):

1. origin = the period's base date (last close before the period);
2. the model sees only prices dated on or before the origin;
3. the universe is computed point in time (``tesina.universe``);
4. the forecast is validated against the M6 submission rules;
5. it is scored with the official RPS and IR over the period's own prices (quintile
   targets computed cross-sectionally within the period).

Transaction costs: at each origin the portfolio moves from the previous weights to
the new ones; ``cost_bps`` times that turnover (sum of absolute weight changes, the
first period counting from cash) is charged on the first day of the period. Results
are reported gross and net. Rebalancing to constant weights within the period, which
the M6 IR assumes, is not charged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tesina.evaluation.ir import information_ratio, portfolio_log_returns
from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.models import Forecast, Model, validate_forecast
from tesina.universe import n_assets_rule, universe


@dataclass
class WalkForwardResult:
    model: str
    policy: str
    cost_bps: float
    periods: pd.DataFrame  # one row per period
    forecasts: dict[str, Forecast] = field(repr=False)
    log_returns: dict[str, pd.Series] = field(repr=False)  # gross daily log returns
    log_returns_net: dict[str, pd.Series] = field(repr=False)

    def summary(self, zero_variance: float = np.nan) -> dict:
        """Mean RPS and pooled IR (gross and net) over all periods."""
        labels = list(self.periods["label"])
        return {
            "model": self.model,
            "policy": self.policy,
            "cost_bps": self.cost_bps,
            "n_periods": len(labels),
            "rps": float(self.periods["rps"].mean()),
            "ir": information_ratio([self.log_returns[k] for k in labels], zero_variance),
            "ir_net": information_ratio([self.log_returns_net[k] for k in labels], zero_variance),
        }


def run(
    model: Model,
    prices: pd.DataFrame,
    calendar: pd.DataFrame,
    policy: str = "official",
    cost_bps: float = 0.0,
    zero_variance: float = np.nan,
) -> WalkForwardResult:
    """Evaluate ``model`` on every period of ``calendar`` (needs ``base_date``/``end_date``)."""
    if not calendar["base_date"].is_monotonic_increasing:
        raise ValueError("walk-forward periods must be in chronological order")
    rows, forecasts, gross, net = [], {}, {}, {}
    previous = pd.Series(dtype=float)
    for period in calendar.itertuples():
        origin = pd.Timestamp(period.base_date)
        history = prices.loc[prices["date"] <= origin].copy()
        assets = universe(history, origin, policy)
        forecast = model.forecast(history, assets, origin)
        validate_forecast(forecast, assets)

        wide = period_prices(prices, period.base_date, period.end_date)[assets]
        targets = quintile_targets(period_returns(wide), n_assets_rule(len(assets)))
        rps = float(rps_per_asset(forecast.probs, targets).mean())
        lr = portfolio_log_returns(wide, forecast.weights)

        index = forecast.weights.index.union(previous.index)
        turnover = float(
            (forecast.weights.reindex(index, fill_value=0) - previous.reindex(index, fill_value=0))
            .abs()
            .sum()
        )
        lr_net = lr.copy()
        lr_net.iloc[0] = np.log1p(np.expm1(lr.iloc[0]) - cost_bps / 1e4 * turnover)
        previous = forecast.weights

        rows.append(
            {
                "k": period.k,
                "label": period.label,
                "origin": origin,
                "end_date": pd.Timestamp(period.end_date),
                "n_assets": len(assets),
                "rps": rps,
                "ir": information_ratio(lr, zero_variance),
                "ir_net": information_ratio(lr_net, zero_variance),
                "turnover": turnover,
            }
        )
        forecasts[period.label], gross[period.label], net[period.label] = forecast, lr, lr_net
    periods = pd.DataFrame(rows)
    return WalkForwardResult(model.name, policy, cost_bps, periods, forecasts, gross, net)
