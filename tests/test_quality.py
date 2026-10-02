"""Data quality checks (issue #13), on synthetic snapshots with planted problems."""

import numpy as np
import pandas as pd
import pytest

from tesina.data import m6
from tesina.data.quality import (
    compare_sources,
    coverage,
    gaps,
    jumps,
    ohlc_problems,
    reference_calendars,
    splits,
    stale_runs,
)
from tesina.evaluation.calendar import m6_calendar, resolve


def make_raw(symbols=("AAA", "BBB", "CCC", "IEFM.L"), start="2021-01-04", end="2021-12-31", seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    frames = []
    for s in symbols:
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
        frames.append(
            pd.DataFrame(
                {
                    "symbol": s,
                    "date": days,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "adjusted_close": close,
                    "volume": 1000,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_clean_snapshot_has_no_findings():
    raw = make_raw()
    calendars = reference_calendars(raw)
    assert gaps(raw, calendars).empty
    assert ohlc_problems(raw).empty
    assert splits(raw).empty
    assert jumps(raw).empty
    assert stale_runs(raw).empty


def test_coverage_flags_missing_late_early_and_delisting():
    raw = make_raw()
    raw = raw[~((raw["symbol"] == "BBB") & (raw["date"] < "2021-03-01"))]
    raw = raw[~((raw["symbol"] == "CCC") & (raw["date"] > "2021-10-01"))]
    out = coverage(
        raw,
        ["AAA", "BBB", "CCC", "DDD", "IEFM.L"],
        start="2021-01-04",
        cutoff_end="2021-12-31",
        delistings={"IEFM.L": pd.Timestamp("2021-06-30")},
    ).set_index("symbol")
    assert out.loc["AAA", "flag"] == ""
    assert out.loc["BBB", "flag"] == "starts_late"
    assert out.loc["CCC", "flag"] == "ends_before_cutoff"
    assert out.loc["DDD", "flag"] == "missing"
    assert out.loc["IEFM.L", "flag"] == "last_date_differs_from_delisting"


def test_gaps_use_the_exchange_calendar():
    raw = make_raw()
    hole = (raw["symbol"] == "AAA") & raw["date"].between("2021-05-03", "2021-05-07")
    raw = raw[~hole]
    out = gaps(raw, reference_calendars(raw))
    assert out.to_dict("records") == [
        {"symbol": "AAA", "from": pd.Timestamp("2021-05-03").date(),
         "to": pd.Timestamp("2021-05-07").date(), "days": 5}
    ]  # fmt: skip
    # A market holiday missing for every symbol of an exchange is not a gap.
    holiday = raw["date"] == "2021-07-05"
    assert gaps(raw[~holiday], reference_calendars(raw[~holiday])).equals(out)


def test_ohlc_problems():
    raw = make_raw()
    raw.loc[0, "low"] = raw.loc[0, "high"] * 2
    raw.loc[1, "adjusted_close"] = -1
    out = ohlc_problems(raw)
    assert set(out["problem"]) == {"high_below_low", "close_outside_range", "nonpositive_price"}


def test_splits_adjusted_and_unadjusted():
    raw = make_raw()
    day = pd.Timestamp("2021-06-01")
    for symbol, adjust in [("AAA", True), ("BBB", False)]:
        after = (raw["symbol"] == symbol) & (raw["date"] >= day)
        raw.loc[after, ["open", "high", "low", "close"]] /= 4  # 4-for-1 split
        if adjust:  # adjusted series: the whole history rescaled, so no jump
            raw.loc[raw["symbol"] == symbol, "adjusted_close"] /= 4
        else:
            raw.loc[after, "adjusted_close"] /= 4
    out = splits(raw).set_index("symbol")
    assert out.loc["AAA", "factor"] == pytest.approx(0.25)
    assert bool(out.loc["AAA", "adjusted"]) is True
    assert bool(out.loc["BBB", "adjusted"]) is False
    flagged = jumps(raw)
    assert list(flagged["symbol"]) == ["BBB"]  # only the unadjusted split moves the series


def test_stale_runs():
    raw = make_raw()
    run = (raw["symbol"] == "CCC") & raw["date"].between("2021-09-01", "2021-09-10")
    raw.loc[run, "adjusted_close"] = 50.0
    out = stale_runs(raw)
    assert out.to_dict("records")[0]["rows"] == 8 and out["symbol"].tolist() == ["CCC"]


def test_compare_sources_on_the_m6_overlap():
    official = m6.load_assets()
    calendar = resolve(m6_calendar("2023-02-17"), official["date"].unique())
    period1 = calendar[calendar["phase"] == "period1"]
    daily, periods = compare_sources(official, official, period1)
    assert (daily["max_abs_diff_bp"] == 0).all()
    assert (periods["share_different_quintile"] == 0).all() and len(periods) == 12

    other = official.copy()
    shock = (other["symbol"] == "IVV") & (other["date"] >= "2022-06-01")
    other.loc[shock, "price"] *= 1.05  # a 5% level shift: one day off by 500 bp
    daily, periods = compare_sources(official, other, period1)
    ivv = daily.set_index("symbol").loc["IVV"]
    assert ivv["max_abs_diff_bp"] == pytest.approx(500, rel=0.03)  # 5% of (1 + r)
    assert (daily.set_index("symbol").drop(index="IVV")["max_abs_diff_bp"] == 0).all()
