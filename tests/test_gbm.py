"""Multiclass GBM (issue #21), including the anti-leakage rules 1-5 of CLAUDE.md."""

import numpy as np
import pandas as pd
import pytest

from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import rps
from tesina.models import RANK_COLUMNS, validate_forecast
from tesina.models.gbm import (
    GBM,
    cross_sectional_features,
    expected_rank_weights,
    price_signals,
    split_windows,
    training_windows,
)

ORIGIN = pd.Timestamp("2024-03-01")
SMALL_GRID = {"num_leaves": [7], "min_data_in_leaf": [50]}


def synthetic_prices(n_assets: int = 40, drift: float = 0.0, seed: int = 0) -> pd.DataFrame:
    """Random walks from 2018; with ``drift`` > 0 each asset has a persistent trend."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2018-01-01", "2024-12-31")
    symbols = [f"S{i:03d}" for i in range(n_assets)]
    mu = drift * np.linspace(-1, 1, n_assets)
    steps = rng.normal(mu, 0.01, (len(days), n_assets))
    df = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=days, columns=symbols)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"})


def to_wide(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pivot(index="date", columns="symbol", values="price").sort_index()  # noqa: PD010


def small_gbm(**kwargs) -> GBM:
    return GBM(grid=SMALL_GRID, max_rounds=200, early_stopping=20, **kwargs)


@pytest.fixture(scope="module")
def prices():
    return synthetic_prices()


@pytest.fixture(scope="module")
def universe(prices):
    return sorted(prices["symbol"].unique())


# ------------------------------------------------------------- rules 1 and 4: splits


def test_split_is_temporal_with_embargo():
    train, val = split_windows(40, n_val=12, embargo=1)
    assert val == list(range(28, 40))
    assert train == list(range(0, 27))
    assert max(train) + 1 < min(val)  # one window of embargo


def test_training_windows_end_at_origin_and_do_not_overlap(prices):
    wide = to_wide(prices[prices["date"] <= ORIGIN])
    windows = training_windows(wide, cross_sectional_features(wide), ORIGIN)
    bases = [w[0] for w in windows]
    ends = [w[1] for w in windows]
    assert bases == sorted(bases)
    assert max(ends) <= ORIGIN
    assert all(b >= e for b, e in zip(bases[1:], ends[:-1], strict=True))


# ------------------------------------------------------------- rule 2: past data only


def test_features_are_causal(prices):
    wide = to_wide(prices)
    full = price_signals(wide)
    cut = price_signals(wide.loc[:ORIGIN])
    for name in full:
        pd.testing.assert_series_equal(full[name].loc[ORIGIN], cut[name].loc[ORIGIN])


def test_forecast_ignores_prices_after_origin(prices, universe):
    future = prices["date"] > ORIGIN
    tampered = prices.copy()
    tampered.loc[future, "price"] *= np.exp(np.random.default_rng(1).normal(0, 0.5, future.sum()))
    a = small_gbm().forecast(prices[~future], universe, ORIGIN)
    b = small_gbm().forecast(tampered, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_hyperparameters_are_validated_on_windows_before_origin(prices, universe):
    model = GBM(grid={"num_leaves": [3, 7], "min_data_in_leaf": [50]}, max_rounds=100)
    model.forecast(prices, universe, ORIGIN)
    log = pd.DataFrame(model.search_log)
    assert len(log) == 2 and log["chosen"].sum() == 1
    assert (log["train_end"] < log["val_start"]).all()
    assert (log["val_end"] <= ORIGIN).all()


# ------------------------------------------------------------- rule 3: cross-sectional


def test_targets_are_quintiles_within_each_window(prices):
    wide = to_wide(prices[prices["date"] <= ORIGIN])
    for base, end, x, targets in training_windows(wide, cross_sectional_features(wide), ORIGIN):
        assert list(x.index) == list(targets.index)
        np.testing.assert_allclose(targets.sum().to_numpy(), len(targets) / 5)
        top = period_returns(wide.loc[base:end])[targets.index].idxmax()
        assert targets.loc[top, "Rank5"] == 1


# ------------------------------------------------------------- rule 5: universe


def test_assets_outside_the_universe_are_ignored(prices, universe):
    members = universe[:30]
    a = small_gbm().forecast(prices[prices["symbol"].isin(members)], members, ORIGIN)
    b = small_gbm().forecast(prices, members, ORIGIN)
    assert list(a.probs.index) == members
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_assets_without_prices_before_a_window_are_not_sampled(prices, universe):
    late = prices[(prices["symbol"] != "S000") | (prices["date"] >= "2023-06-01")]
    wide = to_wide(late[late["date"] <= ORIGIN]).ffill()
    windows = training_windows(wide, cross_sectional_features(wide), ORIGIN)
    for base, _, x, _ in windows:
        assert ("S000" in x.index) == (base >= pd.Timestamp("2023-06-01"))


# ------------------------------------------------------------- behaviour


def test_forecast_is_valid_and_deterministic(prices, universe):
    a = small_gbm().forecast(prices, universe, ORIGIN)
    b = small_gbm().forecast(prices, universe, ORIGIN)
    validate_forecast(a, universe)
    pd.testing.assert_frame_equal(a.probs, b.probs)
    assert (a.weights == 1 / len(universe)).all()


def test_short_history_falls_back_to_uniform(prices, universe):
    model = small_gbm()
    forecast = model.forecast(prices, universe, pd.Timestamp("2019-06-03"))
    validate_forecast(forecast, universe)
    assert (forecast.probs == 0.2).all().all()
    assert model.search_log[-1]["fallback"]


def test_learns_a_persistent_signal():
    prices = synthetic_prices(drift=0.002, seed=3)
    members = sorted(prices["symbol"].unique())
    forecast = small_gbm().forecast(prices, members, ORIGIN)
    after = to_wide(prices).loc[ORIGIN : ORIGIN + pd.Timedelta(days=28)]
    assert rps(forecast.probs, period_returns(after), "proportional") < 0.14


def test_expected_rank_weights():
    probs = pd.DataFrame(
        [[0.6, 0.1, 0.1, 0.1, 0.1], [0.2] * 5, [0.1, 0.1, 0.1, 0.1, 0.6]],
        index=["A", "B", "C"],
        columns=RANK_COLUMNS,
    )
    w = expected_rank_weights(probs)
    assert w["A"] < 0 and w["B"] == 0 and w["C"] > 0
    assert w.abs().sum() == pytest.approx(1.0)
    flat = expected_rank_weights(pd.DataFrame(0.2, index=["A", "B"], columns=RANK_COLUMNS))
    assert (flat == 0.5).all()


def test_expected_rank_forecast_is_valid(prices, universe):
    forecast = small_gbm(weighting="expected_rank").forecast(prices, universe, ORIGIN)
    validate_forecast(forecast, universe)
