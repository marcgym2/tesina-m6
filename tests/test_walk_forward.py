"""Walk-forward harness and baselines (issues #15, #16), including the anti-leakage
rules 1-5 of CLAUDE.md."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pytest

from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.models import RANK_COLUMNS, Forecast, validate_forecast
from tesina.models.baselines import HistoricalFrequency, Uniform, past_windows
from tesina.universe import universe


@pytest.fixture(scope="module")
def prices():
    return m6.load_assets()


@pytest.fixture(scope="module")
def period1(prices):
    calendar = resolve(m6_calendar("2023-02-17"), prices["date"].unique())
    return calendar[calendar["phase"] == "period1"]


def synthetic_prices(seed: int = 0) -> pd.DataFrame:
    """100 assets (two of them DRE and WRK, delisted as in reality) until 2024-12-31."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2022-01-31", "2024-12-31")
    symbols = ["DRE", "WRK"] + [f"S{i:03d}" for i in range(98)]
    paths = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(days), len(symbols))), axis=0))
    df = pd.DataFrame(paths, index=days, columns=symbols)
    df.loc[df.index > "2022-11-28", "DRE"] = np.nan
    df.loc[df.index >= "2024-07-05", "WRK"] = np.nan
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"}).dropna(subset=["price"])


@dataclass
class Spy:
    """Uniform forecast that records what the harness showed it."""

    name: str = "spy"
    seen: list = field(default_factory=list)

    def forecast(self, history, universe, origin):
        self.seen.append((origin, history["date"].max(), len(universe)))
        return Uniform().forecast(history, universe, origin)


# ------------------------------------------------------------------ #16: baselines


def test_uniform_scores_the_official_benchmark_in_period1(prices, period1):
    result = run(Uniform(), prices, period1)
    assert (result.periods["rps"].round(12) == 0.16).all()
    assert result.summary()["ir"] == pytest.approx(0.45346980579, abs=1e-9)


def test_historical_frequency_is_a_valid_forecast(prices, period1):
    result = run(HistoricalFrequency(), prices, period1)
    assert result.periods["rps"].between(0, 1).all()
    first = result.forecasts["1st Submission"].probs
    assert first.sum(axis=1).round(12).eq(1).all()
    assert not np.allclose(first.to_numpy(), 0.2)  # it learns from the pilot window


def test_historical_frequency_counts_past_quintiles():
    days = pd.bdate_range("2022-01-03", "2022-03-31")
    rows = []
    for i, s in enumerate([f"A{i}" for i in range(10)]):
        for t, d in enumerate(days):
            rows.append({"symbol": s, "date": d, "price": 100 * (1 + 0.001 * i) ** t})
    history = pd.DataFrame(rows)
    origin = days[-1]
    f = HistoricalFrequency(alpha=0.0).forecast(history, sorted(history["symbol"].unique()), origin)
    # Asset A9 always has the highest return: quintile 5 in every past window.
    assert f.probs.loc["A9"].tolist() == [0, 0, 0, 0, 1]
    assert f.probs.loc["A0"].tolist() == [1, 0, 0, 0, 0]


# --------------------------------------------------------- anti-leakage (rules 1-5)


def test_rule1_periods_are_temporal_and_ordered(prices, period1):
    spy = Spy()
    run(spy, prices, period1)
    origins = [o for o, _, _ in spy.seen]
    assert origins == sorted(origins) and len(set(origins)) == len(origins)
    shuffled = period1.sample(frac=1, random_state=0)
    with pytest.raises(ValueError, match="chronological"):
        run(Uniform(), prices, shuffled)


def test_rule2_models_only_see_data_up_to_the_origin(prices, period1):
    spy = Spy()
    run(spy, prices, period1)
    assert all(last_seen <= origin for origin, last_seen, _ in spy.seen)


def test_rule2_forecasts_ignore_future_prices(prices, period1):
    cut = period1["base_date"].iloc[5]
    tampered = prices.copy()
    future = tampered["date"] > cut
    tampered.loc[future, "price"] *= np.random.default_rng(1).uniform(0.5, 2, future.sum())
    a = run(HistoricalFrequency(), prices, period1)
    b = run(HistoricalFrequency(), tampered, period1)
    for label in period1.loc[period1["base_date"] <= cut, "label"]:
        pd.testing.assert_frame_equal(a.forecasts[label].probs, b.forecasts[label].probs)


def test_rule3_targets_are_cross_sectional_within_each_period(prices, period1):
    """Changing prices outside a period does not change that period's score."""
    k = period1.iloc[4]
    tampered = prices.copy()
    outside = (tampered["date"] < k.base_date) | (tampered["date"] > k.end_date)
    tampered.loc[outside, "price"] *= 3
    a = run(Uniform(), prices, period1).periods.set_index("label")
    b = run(Uniform(), tampered, period1).periods.set_index("label")
    assert a.loc[k.label, "rps"] == b.loc[k.label, "rps"]
    assert a.loc[k.label, "ir"] == pytest.approx(b.loc[k.label, "ir"])


def test_rule4_past_label_windows_end_at_the_origin():
    days = pd.bdate_range("2022-01-03", "2022-12-30")
    origin = pd.Timestamp("2022-09-16")
    windows = past_windows(days, origin, lookback=None)
    assert windows[0][1] == origin
    assert all(end <= origin for _, end in windows)
    # Consecutive windows touch but do not overlap (four-week labels, four-week step).
    assert all(windows[i + 1][1] == windows[i][0] for i in range(len(windows) - 1))


def test_rule5_universe_is_point_in_time(prices):
    assert "DRE" in universe(prices, "2023-02-03", "official")
    assert "DRE" not in universe(prices, "2023-02-03", "d2")
    history = synthetic_prices()
    assert "WRK" in universe(history, "2024-07-04", "d2")
    assert "WRK" not in universe(history, "2024-07-05", "d2")
    early = universe(prices, "2022-01-31", "official")
    assert len(early) == prices.loc[prices["date"] <= "2022-01-31", "symbol"].nunique()


# ------------------------------------------------------- period 2 (synthetic data)


def test_runs_on_period2_with_policy_d2():
    history = synthetic_prices()
    calendar = resolve(m6_calendar("2024-12-31"), history["date"].unique())
    p2 = calendar[calendar["phase"] == "period2"]
    spy = Spy()
    result = run(spy, history, p2, policy="d2")
    n = result.periods.set_index("origin")["n_assets"]
    assert (n[n.index < "2024-07-05"] == 99).all()  # DRE out from the start
    assert (n[n.index >= "2024-07-05"] == 98).all()  # WRK out after its delisting
    assert result.periods["rps"].round(12).eq(0.16).sum() > 0
    assert np.isfinite(result.summary()["ir"])


# ------------------------------------------------------------ validation and costs


def _forecast(universe, weights):
    probs = pd.DataFrame(0.2, index=universe, columns=RANK_COLUMNS)
    return Forecast(probs, pd.Series(weights, index=universe))


def test_validation_enforces_m6_rules():
    u = ["A", "B", "C", "D"]
    validate_forecast(_forecast(u, [0.25, 0.25, -0.25, 0.25]), u)
    with pytest.raises(ValueError, match="outside"):
        validate_forecast(_forecast(u, [0.5, 0.5, 0.5, 0.0]), u)
    with pytest.raises(ValueError, match="outside"):
        validate_forecast(_forecast(u, [0.05, 0.05, 0.05, 0.05]), u)
    bad = _forecast(u, [0.25] * 4)
    bad.probs.iloc[0] = [0.5, 0.5, 0.5, 0, 0]
    with pytest.raises(ValueError, match="sum to 1"):
        validate_forecast(bad, u)
    with pytest.raises(ValueError, match="one row per"):
        validate_forecast(_forecast(u[:3], [0.3, 0.3, 0.3]), u)


def test_costs_charge_turnover_on_the_first_day(prices, period1):
    gross = run(Uniform(), prices, period1, cost_bps=0)
    net = run(Uniform(), prices, period1, cost_bps=25)
    first = period1["label"].iloc[0]
    expected = [1.0] + [0.0] * (len(period1) - 1)
    np.testing.assert_allclose(net.periods["turnover"], expected, atol=1e-12)
    r_gross = np.expm1(gross.log_returns[first].iloc[0])
    r_net = np.expm1(net.log_returns_net[first].iloc[0])
    assert r_gross - r_net == pytest.approx(25 / 1e4 * net.periods["turnover"].iloc[0])
    later = period1["label"].iloc[3]
    pd.testing.assert_series_equal(net.log_returns_net[later], net.log_returns[later])
