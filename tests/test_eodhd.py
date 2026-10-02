"""EODHD download script and price inputs per phase (issue #12). No network access."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tesina.data import m6
from tesina.data.eodhd import splice

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "download_eodhd.py"
spec = importlib.util.spec_from_file_location("download_eodhd", SCRIPT)
download_eodhd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = download_eodhd
spec.loader.exec_module(download_eodhd)


# ------------------------------------------------------------- download script


def test_symbols_are_the_m6_assets_plus_auxiliary_series():
    assert sorted(download_eodhd.M6_ASSETS) == sorted(m6.load_template()["ID"])
    assert len(set(download_eodhd.SYMBOLS)) == 103


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("IVV", "IVV.US"), ("BF-B", "BF-B.US"), ("IEFM.L", "IEFM.LSE"), ("RE", "EG.US")],
)
def test_eodhd_tickers(symbol, expected):
    assert download_eodhd.ticker(symbol) == expected


def test_parse_keeps_rows_and_separates_warnings():
    payload = [
        {"date": "2024-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5,
         "adjusted_close": 1.4, "volume": 10},
        {"warning": "Data is limited by one year as you have free subscription"},
    ]  # fmt: skip
    df, warnings = download_eodhd.parse("IEFM.L", payload)
    assert list(df.columns) == ["symbol", "ticker", *download_eodhd.COLUMNS]
    assert df.loc[0, "ticker"] == "IEFM.LSE" and len(df) == 1
    assert warnings == ["Data is limited by one year as you have free subscription"]


def test_check_flags_bad_series():
    good = pd.DataFrame({"date": ["2024-01-02", "2024-01-03"], "adjusted_close": [1.0, 1.1]})
    assert download_eodhd.check(good) == []
    assert download_eodhd.check(good.iloc[:0]) == ["no rows"]
    bad = pd.DataFrame({"date": ["2024-01-03", "2024-01-03"], "adjusted_close": [1.0, -1.0]})
    assert set(download_eodhd.check(bad)) == {"duplicated dates", "non-positive adjusted_close"}


def test_api_key_is_never_in_error_messages(monkeypatch):
    import io
    import urllib.error

    def fail(url, timeout):
        raise urllib.error.HTTPError(url, 401, "x", {}, io.BytesIO(b"bad token SECRET123"))

    monkeypatch.setattr(download_eodhd.urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError) as error:
        download_eodhd.get_json("eod/IVV.US", "SECRET123")
    assert "SECRET123" not in str(error.value)


# ------------------------------------------------------------- price inputs


def frame(symbol, dates, prices):
    return pd.DataFrame({"symbol": symbol, "date": pd.to_datetime(dates), "price": prices})


def test_splice_rescales_history_and_keeps_official_prices():
    dates = pd.bdate_range("2022-01-24", "2022-02-04")
    history = frame("A", dates, np.linspace(50, 60, len(dates)))
    official = frame("A", dates[dates >= "2022-01-31"], [100.0, 101, 102, 103, 104])
    out = splice(history, official)

    pd.testing.assert_frame_equal(
        out[out["date"] >= "2022-01-31"].reset_index(drop=True), official.reset_index(drop=True)
    )
    hist = history.set_index("date")["price"]
    ratio = 100.0 / hist.loc["2022-01-31"]
    before = out[out["date"] < "2022-01-31"].set_index("date")["price"]
    np.testing.assert_allclose(before, hist.loc[:"2022-01-28"] * ratio)
    # The return across the splice is the history's own return: no artificial jump.
    spliced = out.set_index("date")["price"]
    assert spliced.loc["2022-01-31"] / spliced.loc["2022-01-28"] == pytest.approx(
        hist.loc["2022-01-31"] / hist.loc["2022-01-28"]
    )


def test_splice_keeps_auxiliary_series_and_assets_without_history():
    dates = pd.bdate_range("2022-01-24", "2022-02-04")
    history = frame("VIXY", dates, 10.0)
    official = frame("B", dates[dates >= "2022-01-31"], 5.0)
    out = splice(history, official)
    assert (out["symbol"] == "VIXY").sum() == len(dates)
    assert (out["symbol"] == "B").sum() == 5


def test_splice_anchors_on_last_history_date_before_the_official_start():
    history = frame("A", ["2022-01-27", "2022-01-28"], [10.0, 20.0])
    official = frame("A", ["2022-01-31"], [40.0])
    out = splice(history, official).set_index("date")["price"]
    assert out.loc["2022-01-28"] == 40.0 and out.loc["2022-01-27"] == 20.0


def test_auxiliary_series_add_no_trading_days_to_the_official_window():
    history = frame(
        "VIXY", ["2022-01-28", "2022-01-31", "2022-02-21", "2022-02-22", "2023-03-01"], 1.0
    )
    official = frame("A", ["2022-01-31", "2022-02-22"], 5.0)
    out = splice(history, official)
    vixy = set(out.loc[out["symbol"] == "VIXY", "date"].dt.strftime("%Y-%m-%d"))
    assert vixy == {"2022-01-28", "2022-01-31", "2022-02-22"}


def test_period1_input_reproduces_the_official_benchmark():
    """With synthetic history and an auxiliary series spliced in, the uniform benchmark
    still scores exactly what it scores on the official data alone."""
    from tesina.backtest.walk_forward import run
    from tesina.evaluation.calendar import m6_calendar, resolve
    from tesina.models.baselines import Uniform

    official = m6.load_assets()
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2019-01-01", "2023-06-30")  # includes US and UK holidays
    symbols = [*official["symbol"].unique(), "VIXY"]
    history = pd.concat(
        frame(s, days, 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))) for s in symbols
    )
    prices = splice(history, official)
    calendar = resolve(m6_calendar("2023-02-17"), prices["date"].unique())
    period1 = calendar[calendar["phase"] == "period1"]
    assets = sorted(official["symbol"].unique())
    result = run(Uniform(), prices, period1, assets=assets)
    assert result.summary()["ir"] == pytest.approx(0.45346980579, abs=1e-9)
    assert (result.periods["rps"].round(12) == 0.16).all()


def test_sebrad_group_lists_its_extended_universe():
    symbols = download_eodhd.group_symbols("sebrad")
    assert len(symbols) == 1163 and len(set(symbols)) == 1163
    assert download_eodhd.GROUPS["sebrad"][2] is False  # missing symbols do not abort
    assert download_eodhd.GROUPS["core"][2] is True
