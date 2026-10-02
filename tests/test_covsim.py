"""Simulation from covariances (issue #22), including the anti-leakage rules 1-5."""

import numpy as np
import pandas as pd
import pytest

from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import rps
from tesina.models import validate_forecast
from tesina.models.covsim import CovarianceSimulation, ewma_covariance, simulate_quintile_probs

ORIGIN = pd.Timestamp("2023-03-03")


def synthetic_prices(n_assets: int = 40, seed: int = 0, vol_spread: bool = True) -> pd.DataFrame:
    """Zero-drift random walks from 2020; vols from 0.5% to 3% a day if ``vol_spread``."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2020-01-01", "2023-12-29")
    symbols = [f"S{i:03d}" for i in range(n_assets)]
    sigma = np.linspace(0.005, 0.03, n_assets) if vol_spread else np.full(n_assets, 0.01)
    steps = rng.normal(0, 1, (len(days), n_assets)) * sigma
    df = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=days, columns=symbols)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"})


def to_wide(prices):
    return prices.pivot(index="date", columns="symbol", values="price").sort_index()  # noqa: PD010


def small(**kwargs) -> CovarianceSimulation:
    return CovarianceSimulation(halflives=(21, 126), n_sims=2000, **kwargs)


@pytest.fixture(scope="module")
def prices():
    return synthetic_prices()


@pytest.fixture(scope="module")
def universe(prices):
    return sorted(prices["symbol"].unique())


# ------------------------------------------------------------- building blocks


def test_ewma_covariance_matches_the_formula():
    rng = np.random.default_rng(0)
    daily = pd.DataFrame(rng.normal(0, 0.01, (300, 3)))
    cov = ewma_covariance(daily, halflife=20)
    r = daily.to_numpy()[-100:]
    w = 0.5 ** (np.arange(100)[::-1] / 20)
    expected = (r * w[:, None]).T @ r / w.sum()
    np.testing.assert_allclose(cov, expected, atol=1e-12)


def test_ewma_covariance_handles_short_histories():
    rng = np.random.default_rng(0)
    daily = pd.DataFrame(rng.normal(0, 0.01, (300, 3)))
    daily.iloc[:-5, 2] = np.nan  # only 5 observations
    cov = ewma_covariance(daily, halflife=20)
    assert cov[2, 0] == 0 and cov[2, 1] == 0
    assert cov[2, 2] == pytest.approx(np.median(np.diag(cov)[:2]))
    assert np.linalg.eigvalsh(cov).min() >= -1e-15


def test_simulated_probabilities():
    n = 10
    sigma = np.linspace(0.01, 0.05, n)
    probs = simulate_quintile_probs(np.diag(sigma**2), n_sims=20_000, seed=0)
    np.testing.assert_allclose(probs.sum(axis=1), 1)
    np.testing.assert_allclose(probs.sum(axis=0), n / 5)  # two assets per quintile
    # Mean zero: symmetric tails; the most volatile asset is the most extreme.
    np.testing.assert_allclose(probs[:, 0], probs[:, 4], atol=0.02)
    assert probs[-1, [0, 4]].sum() > probs[0, [0, 4]].sum()
    equal = simulate_quintile_probs(np.eye(n), n_sims=20_000, seed=0)
    np.testing.assert_allclose(equal, 0.2, atol=0.015)


# ------------------------------------------------------------- rules 1, 2 and 4


def test_forecast_ignores_prices_after_origin(prices, universe):
    future = prices["date"] > ORIGIN
    tampered = prices.copy()
    tampered.loc[future, "price"] *= 3
    a = small().forecast(prices[~future], universe, ORIGIN)
    b = small().forecast(tampered, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_halflife_is_chosen_on_past_windows(prices, universe):
    model = small()
    model.forecast(prices, universe, ORIGIN)
    log = pd.DataFrame(model.search_log)
    assert list(log["halflife"]) == [21, 126]
    assert log["chosen"].sum() == 1
    assert (log["val_end"] <= ORIGIN).all()
    assert (log["n_val_windows"] == 12).all()


def test_no_history_falls_back_to_the_default_halflife(prices, universe):
    model = small()
    forecast = model.forecast(prices, universe, pd.Timestamp("2020-01-20"))
    validate_forecast(forecast, universe)
    assert model.search_log[-1]["fallback"]


# ------------------------------------------------------------- rules 3 and 5


def test_probabilities_are_cross_sectional_quintiles(prices, universe):
    forecast = small().forecast(prices, universe, ORIGIN)
    np.testing.assert_allclose(forecast.probs.sum().to_numpy(), len(universe) / 5)


def test_assets_outside_the_universe_are_ignored(prices, universe):
    members = universe[::2]
    a = small().forecast(prices[prices["symbol"].isin(members)], members, ORIGIN)
    b = small().forecast(prices, members, ORIGIN)
    assert list(a.probs.index) == members
    pd.testing.assert_frame_equal(a.probs, b.probs)


# ------------------------------------------------------------- behaviour


def test_forecast_is_valid_and_deterministic(prices, universe):
    a = small().forecast(prices, universe, ORIGIN)
    b = small().forecast(prices, universe, ORIGIN)
    validate_forecast(a, universe)
    pd.testing.assert_frame_equal(a.probs, b.probs)
    assert (a.weights == 1 / len(universe)).all()


def test_beats_uniform_when_volatilities_differ(prices, universe):
    wide = to_wide(prices)
    scores = []
    for nominal in pd.date_range("2022-01-07", periods=6, freq="28D"):
        origin = wide.index[wide.index.searchsorted(nominal, "right") - 1]
        forecast = small().forecast(prices, universe, origin)
        after = wide.loc[origin : origin + pd.Timedelta(days=28)]
        scores.append(rps(forecast.probs, period_returns(after), "proportional"))
    assert max(scores) < 0.16
    assert np.mean(scores) < 0.158


def test_close_to_uniform_when_volatilities_are_equal():
    prices = synthetic_prices(vol_spread=False, seed=1)
    members = sorted(prices["symbol"].unique())
    forecast = small().forecast(prices, members, ORIGIN)
    assert (forecast.probs - 0.2).abs().to_numpy().max() < 0.1
