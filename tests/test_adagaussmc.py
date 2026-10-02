"""AdaGaussMC reimplementation (issue #20), including the anti-leakage rules 1-5."""

import numpy as np
import pandas as pd
import pytest

from tesina.data import m6
from tesina.evaluation.prices import period_returns
from tesina.evaluation.rps import rps
from tesina.models import validate_forecast
from tesina.models.adagaussmc import AdaGaussMC, adavol_forecast, asset_class

ORIGIN = pd.Timestamp("2022-03-04")


def garch_path(n, omega, alpha, beta, rng):
    s2 = omega / (1 - alpha - beta)
    x, var = np.empty(n), np.empty(n + 1)
    var[0] = s2
    for t in range(n):
        x[t] = np.sqrt(s2) * rng.standard_normal()
        s2 = omega + alpha * x[t] ** 2 + beta * s2
        var[t + 1] = s2
    return x, var


def synthetic_prices(symbols, scales, seed=0, start="2014-06-02", end="2022-12-30"):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    cols = {}
    for s, k in zip(symbols, scales, strict=True):
        x, _ = garch_path(len(days), 1e-6 * k**2, 0.08, 0.90, rng)
        cols[s] = 100 * np.exp(np.cumsum(x))
    df = pd.DataFrame(cols, index=days)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"})


@pytest.fixture(scope="module")
def universe():
    stocks = ["ABBV", "ACN", "AEP", "AIZ", "ALLE", "AMAT", "AMP", "AMZN"]
    etfs = ["IVV", "IWM", "EWU", "EWG", "LQD", "HYG", "SHY", "IEF", "IAU", "SLV"]
    return sorted([*stocks, *etfs, "VXX"])


@pytest.fixture(scope="module")
def prices(universe):
    scale = {"stock": 3.0, "etf_fixed_income": 0.3}
    scales = [scale.get(asset_class(s), 1.0) for s in universe]
    return synthetic_prices(universe, scales)


def model(**kwargs):
    return AdaGaussMC(n_sims=5000, **kwargs)


# ------------------------------------------------------------- building blocks


def test_asset_classes_follow_the_paper():
    assets = sorted(m6.load_template()["ID"])
    counts = pd.Series([asset_class(s) for s in assets]).value_counts().to_dict()
    assert counts == {
        "stock": 50,
        "etf_equities": 37,
        "etf_fixed_income": 9,
        "etf_commodities": 3,
        "etf_volatility": 1,
    }


def test_simplex_projection_is_euclidean():
    from tesina.models.adagaussmc import adavol_module

    module = adavol_module()
    w = module.euclidean_proj_simplex(np.array([2.0, 0.1]), s=1)
    np.testing.assert_allclose(w, [1.0, 0.0])  # the notebook's version returns [0, 0]
    w = module.euclidean_proj_simplex(np.array([0.6, 0.5, 0.1]), s=1)
    np.testing.assert_allclose(w, np.array([0.6, 0.5, 0.1]) - 0.2 / 3)
    w = module.euclidean_proj_simplex(np.array([0.9, 0.6, 0.0]), s=1)
    np.testing.assert_allclose(w, [0.65, 0.35, 0.0])
    assert w.sum() == pytest.approx(1.0)


def test_adavol_tracks_conditional_variance():
    rng = np.random.default_rng(1)
    x, var = garch_path(3000, 1e-6, 0.08, 0.90, rng)
    forecasts = [adavol_forecast(x[:n]) for n in (1000, 2000, 3000)]
    truth = [var[n] for n in (1000, 2000, 3000)]
    assert np.corrcoef(np.log(forecasts), np.log(truth))[0, 1] > 0.5
    # Scaling the returns scales the variance forecast (the model has no fixed level).
    assert adavol_forecast(10 * x) == pytest.approx(100 * adavol_forecast(x), rel=1e-6)


# ------------------------------------------------------------- rules 1, 2 and 4


def test_forecast_ignores_prices_after_origin(prices, universe):
    future = prices["date"] > ORIGIN
    tampered = prices.copy()
    tampered.loc[future, "price"] *= 4
    a = model().forecast(prices[~future], universe, ORIGIN)
    b = model().forecast(tampered, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_class_means_use_only_their_window(prices, universe):
    m = model()
    m.forecast(prices, universe, ORIGIN)
    later = prices.copy()
    late = (later["date"] > "2020-12-31") & (later["date"] <= ORIGIN)
    later.loc[late, "price"] *= 1.5  # a jump after the window
    m2 = model()
    m2.forecast(later, universe, ORIGIN)
    assert m.log[-1]["class_means"] == m2.log[-1]["class_means"]


# ------------------------------------------------------------- rules 3 and 5


def test_probabilities_are_cross_sectional_quintiles(prices, universe):
    forecast = model().forecast(prices, universe, ORIGIN)
    validate_forecast(forecast, universe)
    n = len(universe)
    sizes = np.bincount(np.searchsorted([k * n / 5 for k in range(1, 5)], np.arange(1, n + 1)))
    np.testing.assert_allclose(forecast.probs.sum().to_numpy(), sizes)


def test_assets_outside_the_universe_are_ignored(prices, universe):
    members = [s for s in universe if s != "AMZN"]
    a = model().forecast(prices[prices["symbol"].isin(members)], members, ORIGIN)
    b = model().forecast(prices, members, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


# ------------------------------------------------------------- behaviour


def test_volatile_assets_get_extreme_quintiles(prices, universe):
    probs = model().forecast(prices, universe, ORIGIN).probs
    extremes = probs["Rank1"] + probs["Rank5"]
    stocks = [s for s in universe if asset_class(s) == "stock"]
    bonds = [s for s in universe if asset_class(s) == "etf_fixed_income"]
    assert extremes[stocks].mean() > extremes[bonds].mean() + 0.2


def test_beats_uniform_when_volatilities_differ(prices, universe):
    wide = prices.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    scores = []
    for nominal in pd.date_range("2022-03-04", periods=6, freq="28D"):
        origin = wide.index[wide.index.searchsorted(nominal, "right") - 1]
        forecast = model().forecast(prices, universe, origin)
        after = wide.loc[origin : origin + pd.Timedelta(days=28)]
        scores.append(rps(forecast.probs, period_returns(after), "proportional"))
    assert np.mean(scores) < 0.155


def test_forecast_is_deterministic_and_uses_benchmark_weights(prices, universe):
    a = model().forecast(prices, universe, ORIGIN)
    b = model().forecast(prices, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)
    assert (a.weights == 1 / len(universe)).all()


def test_short_histories_fall_back_to_class_median(universe):
    prices = synthetic_prices(universe, [1.0] * len(universe))
    late = prices[(prices["symbol"] != "ABBV") | (prices["date"] > ORIGIN - pd.Timedelta(days=10))]
    forecast = model().forecast(late, universe, ORIGIN)
    validate_forecast(forecast, universe)
