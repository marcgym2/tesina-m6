"""RScriptModel: the bridge to participants' R code (issues #17, #18)."""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tesina.backtest.walk_forward import run
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.models.baselines import Uniform
from tesina.models.external import RScriptModel

FAKE = Path(__file__).parent / "data" / "fake_r_model"
needs_r = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")


def history() -> pd.DataFrame:
    days = pd.bdate_range("2022-01-03", "2022-03-31")
    trend = {"A": 1.001, "B": 0.999, "VXX": 0.995, "VIXY": 1.004, "EXTRA": 1.0}
    rows = [
        {"symbol": s, "date": d, "price": 100 * g**t}
        for s, g in trend.items()
        for t, d in enumerate(days)
    ]
    return pd.DataFrame(rows)


def test_prices_frame_applies_substitutes_and_cuts_at_origin():
    model = RScriptModel("fake", FAKE, substitutes={"VXX": "VIXY"}, extra_symbols=["EXTRA"])
    origin = pd.Timestamp("2022-02-25")
    h = history()
    wide = model.prices_frame(h[h["date"] <= origin], ["A", "B", "VXX"])
    assert list(wide.columns) == ["A", "B", "EXTRA", "VXX"]
    assert wide.index.max() == origin
    vixy = h[(h["symbol"] == "VIXY") & (h["date"] <= origin)].set_index("date")["price"]
    pd.testing.assert_series_equal(wide["VXX"], vixy, check_names=False)


@needs_r
def test_forecast_round_trip_through_r():
    model = RScriptModel("fake", FAKE, substitutes={"VXX": "VIXY"})
    f = model.forecast(history(), ["A", "B", "VXX"], pd.Timestamp("2022-02-25"))
    assert f.probs.loc["A"].tolist() == [0, 0, 0, 0, 1]
    assert f.probs.loc["B"].tolist() == [1, 0, 0, 0, 0]
    # VXX falls, but the model saw VIXY (rising) in its place.
    assert f.probs.loc["VXX"].tolist() == [0, 0, 0, 0, 1]
    assert np.allclose(f.weights, 1 / 3)


@needs_r
def test_missing_forecast_raises(monkeypatch):
    monkeypatch.setenv("FAKE_DROP", "B")
    model = RScriptModel("fake", FAKE)
    with pytest.raises(ValueError, match="no forecast"):
        model.forecast(history(), ["A", "B"], pd.Timestamp("2022-02-25"))


def test_auxiliary_series_stay_out_of_the_evaluated_universe():
    h = history()
    calendar = resolve(m6_calendar("2022-03-31"), h["date"].unique())
    calendar = calendar[calendar["k"] == 0].assign(base_date=pd.Timestamp("2022-02-04"))
    result = run(Uniform(), h, calendar, assets=["A", "B", "VXX"])
    assert result.periods["n_assets"].tolist() == [3]
    assert set(result.forecasts["Trial run"].probs.index) == {"A", "B", "VXX"}
