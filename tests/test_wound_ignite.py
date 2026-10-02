"""PythonScriptModel bridge and the wound-ignite adapter (issue #19)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tesina.models import validate_forecast
from tesina.models.external import PythonScriptModel

ROOT = Path(__file__).resolve().parent.parent
FAKE = ROOT / "tests" / "data" / "fake_py_model"
VENDOR = ROOT / "vendor" / "wound-ignite"


def synthetic_prices(symbols, start="2021-01-01", end="2022-06-30", seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    paths = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(days), len(symbols))), axis=0))
    df = pd.DataFrame(paths, index=days, columns=symbols)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"})


def test_python_script_model_passes_only_the_past_and_reads_decisions():
    symbols = ["A", "B", "C", "D"]
    prices = synthetic_prices(symbols)
    origin = pd.Timestamp("2022-03-04")
    model = PythonScriptModel("fake", FAKE, args=["--seed", "3"], decisions=True)
    forecast = model.forecast(prices, symbols, origin)
    validate_forecast(forecast, symbols)
    assert forecast.weights.tolist() == [-0.25, 0.25, -0.25, 0.25]
    plain = PythonScriptModel("fake", FAKE).forecast(prices, symbols, origin)
    assert (plain.weights == 0.25).all()


def test_rounding_residue_in_decisions_is_scaled_but_real_breaches_fail():
    symbols = ["A", "B", "C", "D"]
    prices = synthetic_prices(symbols)
    origin = pd.Timestamp("2022-03-04")
    residue = PythonScriptModel("fake", FAKE, args=["--gross", "1.0001"], decisions=True)
    assert residue.forecast(prices, symbols, origin).weights.abs().sum() == pytest.approx(1.0)
    breach = PythonScriptModel("fake", FAKE, args=["--gross", "1.2"], decisions=True)
    with pytest.raises(ValueError, match="outside"):
        validate_forecast(breach.forecast(prices, symbols, origin), symbols)


@pytest.mark.skipif(not (VENDOR / ".venv").exists(), reason="uv sync --project vendor/wound-ignite")
def test_wound_ignite_adapter_runs_and_is_reproducible():
    symbols = [f"S{i}" for i in range(10)]
    prices = synthetic_prices(symbols)
    origin = pd.Timestamp("2022-06-03")
    a = PythonScriptModel("wi", VENDOR, args=["--seed", "1"], decisions=True)
    fa = a.forecast(prices, symbols, origin)
    fb = a.forecast(prices, symbols, origin)
    validate_forecast(fa, symbols)
    pd.testing.assert_frame_equal(fa.probs, fb.probs)
    # Prices after the origin never reach the adapter.
    tampered = prices.copy()
    tampered.loc[tampered["date"] > origin, "price"] *= 10
    pd.testing.assert_frame_equal(a.forecast(tampered, symbols, origin).probs, fa.probs)
    other = PythonScriptModel("wi", VENDOR, args=["--seed", "2"]).forecast(prices, symbols, origin)
    assert not other.probs.equals(fa.probs)  # the seed drives the Monte Carlo
