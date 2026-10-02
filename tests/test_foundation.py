"""Zero-shot foundation model adapter (issue #23), including the anti-leakage rules 1-5.

The tests use fake backends; the real TimesFM-3 test runs only when the pinned weights
are already in the local Hugging Face cache.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from tesina.models import validate_forecast
from tesina.models.foundation import CHECKPOINT, DECILES, REVISION, TimesFM, quantile_function

ORIGIN = pd.Timestamp("2023-03-03")


def synthetic_prices(n_assets: int = 30, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2019-01-01", "2023-12-29")
    symbols = [f"S{i:03d}" for i in range(n_assets)]
    sigma = np.linspace(0.005, 0.03, n_assets)
    steps = rng.normal(0, 1, (len(days), n_assets)) * sigma
    df = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=days, columns=symbols)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"})


@dataclass
class RandomWalkBackend:
    """Deciles of a Gaussian random walk with the context's daily volatility.

    ``drift`` maps a series' last value to a daily drift, so tests can make some
    assets look better than others. Records every context it is shown.
    """

    drift: object = None
    seen: list = field(default_factory=list)

    def __call__(self, contexts, horizon):
        self.seen.append([c.copy() for c in contexts])
        out = []
        for c in contexts:
            sd = np.std(np.diff(c[-250:])) if len(c) > 2 else 0.01
            mu = 0.0 if self.drift is None else self.drift(c)
            steps = np.arange(1, horizon + 1)[:, None]
            out.append(c[-1] + mu * steps + sd * np.sqrt(steps) * norm.ppf(DECILES)[None, :])
        return np.stack(out)


@pytest.fixture(scope="module")
def prices():
    return synthetic_prices()


@pytest.fixture(scope="module")
def universe(prices):
    return sorted(prices["symbol"].unique())


def model(**kwargs) -> TimesFM:
    kwargs.setdefault("backend", RandomWalkBackend())
    return TimesFM(n_sims=4000, **kwargs)


# ------------------------------------------------------------- quantile function


def test_quantile_function_interpolates_deciles_and_has_gaussian_tails():
    deciles = (0.01 + 0.05 * norm.ppf(DECILES))[None, :]
    u = np.array([[0.001], [0.05], [0.1], [0.35], [0.5], [0.9], [0.97], [0.999]])
    expected = 0.01 + 0.05 * norm.ppf(u)
    got = quantile_function(deciles, u)
    np.testing.assert_allclose(got[[0, 1, 2, 4, 5, 6, 7]], expected[[0, 1, 2, 4, 5, 6, 7]])
    assert abs(got[3, 0] - expected[3, 0]) < 0.002  # linear between deciles
    assert np.all(
        np.diff(quantile_function(deciles, np.linspace(1e-6, 1 - 1e-6, 999)[:, None]), axis=0) >= 0
    )


def test_quantile_function_repairs_crossing_deciles():
    deciles = np.array([[-2, -1, 0, -0.5, 0, 0.5, 1, 1.5, 2.0]])
    values = quantile_function(deciles, np.linspace(0.01, 0.99, 99)[:, None])
    assert np.all(np.diff(values[:, 0]) >= 0)


# ------------------------------------------------------------- rules 1, 2 and 4


def test_contexts_end_at_origin_and_have_fixed_length(prices, universe):
    backend = RandomWalkBackend()
    model(backend=backend, context=500).forecast(prices, universe, ORIGIN)
    wide = prices.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    expected_last = np.log(wide.loc[:ORIGIN].iloc[-1]).to_numpy()
    contexts = backend.seen[-1]
    assert all(len(c) == 500 for c in contexts)
    np.testing.assert_allclose([c[-1] for c in contexts], expected_last, rtol=1e-6)


def test_forecast_ignores_prices_after_origin(prices, universe):
    future = prices["date"] > ORIGIN
    tampered = prices.copy()
    tampered.loc[future, "price"] *= 5
    a = model().forecast(prices[~future], universe, ORIGIN)
    b = model().forecast(tampered, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


# ------------------------------------------------------------- rules 3 and 5


def test_probabilities_are_cross_sectional_quintiles(prices, universe):
    forecast = model().forecast(prices, universe, ORIGIN)
    validate_forecast(forecast, universe)
    np.testing.assert_allclose(forecast.probs.sum().to_numpy(), len(universe) / 5)


def test_assets_outside_the_universe_are_ignored(prices, universe):
    members = universe[::2]
    a = model().forecast(prices[prices["symbol"].isin(members)], members, ORIGIN)
    b = model().forecast(prices, members, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_short_series_take_the_median_deciles(prices, universe):
    late = prices[(prices["symbol"] != "S000") | (prices["date"] > ORIGIN - pd.Timedelta(days=20))]
    m = model()
    m.forecast(late, universe, ORIGIN)
    deciles = m.deciles_log[ORIGIN]
    pd.testing.assert_series_equal(
        deciles.loc["S000"], deciles.drop(index="S000").median(), check_names=False
    )


# ------------------------------------------------------------- behaviour


def test_volatile_assets_get_extreme_quintiles(prices, universe):
    probs = model().forecast(prices, universe, ORIGIN).probs
    extremes = probs["Rank1"] + probs["Rank5"]
    assert extremes.iloc[-5:].mean() > extremes.iloc[:5].mean() + 0.2


def test_forecast_median_shifts_quintiles_and_expected_rank_weights(prices, universe):
    favourite = {}

    def drift(c):  # +0.5% a day for the series whose last value is S029's
        return 0.005 if np.isclose(c[-1], favourite["S029"]) else 0.0

    wide = prices.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    favourite["S029"] = float(np.log(wide.loc[:ORIGIN, "S029"].iloc[-1]))
    forecast = model(backend=RandomWalkBackend(drift), weighting="expected_rank").forecast(
        prices, universe, ORIGIN
    )
    validate_forecast(forecast, universe)
    assert forecast.probs.loc["S029", "Rank5"] > 0.5
    assert forecast.weights.idxmax() == "S029"


def test_forecast_is_deterministic(prices, universe):
    a = model().forecast(prices, universe, ORIGIN)
    b = model().forecast(prices, universe, ORIGIN)
    pd.testing.assert_frame_equal(a.probs, b.probs)


def test_backend_shape_is_checked(prices, universe):
    with pytest.raises(ValueError, match="shape"):
        model(backend=lambda contexts, horizon: np.zeros((len(contexts), horizon, 10))).forecast(
            prices, universe, ORIGIN
        )


# ------------------------------------------------------------- real TimesFM-3


def weights_cached() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        path = try_to_load_from_cache(CHECKPOINT, "model.safetensors", revision=REVISION)
        return isinstance(path, str)
    except ImportError:
        return False


@pytest.mark.skipif(not weights_cached(), reason="TimesFM-3 weights not in the local cache")
def test_timesfm3_backend_returns_deciles(prices, universe):
    from tesina.models.foundation import TimesFM3Backend

    backend = TimesFM3Backend()
    rng = np.random.default_rng(0)
    contexts = [np.cumsum(rng.normal(0, 0.01, 600)).astype(np.float32) + 4.6 for _ in range(3)]
    q = backend(contexts, 20)
    assert q.shape == (3, 20, 9)
    assert np.all(np.diff(q, axis=2) >= -1e-6)
    forecast = TimesFM(backend=backend, n_sims=2000).forecast(prices, universe, ORIGIN)
    validate_forecast(forecast, universe)
