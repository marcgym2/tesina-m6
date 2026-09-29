"""RPS/IR against the official worked example, the official leaderboard and the R rules."""

import numpy as np
import openpyxl
import pandas as pd
import pytest

from tesina.data import m6
from tesina.evaluation.ir import information_ratio, portfolio_log_returns
from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import RANK_COLUMNS, quintile_targets, rps, rps_per_asset

SHEET_TO_SUMMARY = {"Pilot": "Pilot", **{f"Month{i}": f"M{i}" for i in range(1, 13)}}


@pytest.fixture(scope="module")
def assets():
    return m6.load_assets()


@pytest.fixture(scope="module")
def calendar():
    return m6.load_period1_calendar()


@pytest.fixture(scope="module")
def windows(assets, calendar):
    return {
        c.evaluation: period_prices(assets, c.base_date, c.end_date) for c in calendar.itertuples()
    }


@pytest.fixture(scope="module")
def excel_summary():
    wb = openpyxl.load_workbook(m6.path("evaluation_example"), data_only=True, read_only=True)
    rows = list(wb["Summary"].iter_rows(values_only=True))
    wb.close()
    monthly = {r[0]: (r[1], r[2]) for r in rows[1:] if r[0]}
    quarterly = {r[4]: (r[5], r[6]) for r in rows[1:] if r[4]}
    return monthly, quarterly, (rows[1][9], rows[1][10])


# ---------------------------------------------------------------- official worked example


def test_calendar_matches_price_data(calendar, windows):
    for c in calendar.itertuples():
        assert len(windows[c.evaluation]) - 1 == c.n_days
    assert calendar["n_days"].tolist() == [20, 20, 19, 20, 20, 20, 20, 20, 20, 20, 20, 19, 20]


def test_benchmark_matches_excel_by_month(calendar, windows, excel_summary):
    monthly, _, _ = excel_summary
    template = m6.load_template().set_index("ID")
    for c in calendar.itertuples():
        wide = windows[c.evaluation]
        excel_rps, excel_ir = monthly[SHEET_TO_SUMMARY[c.sheet]]
        assert rps(template, period_returns(wide)) == pytest.approx(excel_rps, abs=1e-12)
        ir = information_ratio(portfolio_log_returns(wide, template["Decision"]))
        assert ir == pytest.approx(excel_ir, abs=1e-10)


def test_benchmark_matches_excel_by_quarter_and_global(calendar, windows, excel_summary):
    _, quarterly, (global_rps, global_ir) = excel_summary
    weights = m6.load_template().set_index("ID")["Decision"]
    months = m6.EVALUATIONS[1:]
    rets = {e: portfolio_log_returns(windows[e], weights) for e in months}
    for q in range(4):
        ir = information_ratio([rets[e] for e in months[3 * q : 3 * q + 3]])
        assert ir == pytest.approx(quarterly[f"Q{q + 1}"][1], abs=1e-10)
    assert information_ratio([rets[e] for e in months]) == pytest.approx(global_ir, abs=1e-10)
    assert global_rps == pytest.approx(0.16)


# ------------------------------------------------------------------- official leaderboard


def test_every_team_month_matches_official_leaderboard(windows):
    """All 2,482 team x evaluation scores; the leaderboard is rounded to 5 decimals."""
    subs = m6.load_submissions()
    board = m6.load_leaderboard().set_index(["team", "evaluation"])
    targets = {e: quintile_targets(period_returns(w)) for e, w in windows.items()}
    worst_rps = worst_ir = 0.0
    for (team, evaluation), row in board.iterrows():
        sub = subs[(subs["Team"] == team) & (subs["Evaluation"] == evaluation)].set_index("Symbol")
        assert len(sub) == 100, (team, evaluation)
        score_rps = rps_per_asset(sub, targets[evaluation]).mean()
        lr = portfolio_log_returns(windows[evaluation], sub["Decision"])
        score_ir = information_ratio(lr, zero_variance=1.0)
        worst_rps = max(worst_rps, abs(score_rps - row["rps"]))
        worst_ir = max(worst_ir, abs(score_ir - row["ir"]))
    assert len(board) == 2482
    assert worst_rps < 6e-6
    assert worst_ir < 6e-6


# --------------------------------------------------------------------- rules of the R code


def _returns(values):
    return pd.Series(values, index=[f"A{i:03d}" for i in range(len(values))], dtype=float)


def test_quintiles_without_ties():
    t = quintile_targets(_returns(np.arange(100)))
    assert (t.sum(axis=1) == 1).all()
    assert t.iloc[0].tolist() == [1, 0, 0, 0, 0]  # worst return -> quintile 1
    assert t.iloc[19].tolist() == [1, 0, 0, 0, 0]
    assert t.iloc[20].tolist() == [0, 1, 0, 0, 0]
    assert t.iloc[99].tolist() == [0, 0, 0, 0, 1]


def test_tie_straddling_quintiles_is_averaged():
    values = np.arange(100, dtype=float)
    values[20] = values[19]  # positions 20 and 21 tied
    t = quintile_targets(_returns(values))
    assert t.iloc[19].tolist() == [0.5, 0.5, 0, 0, 0]
    assert t.iloc[20].tolist() == [0.5, 0.5, 0, 0, 0]
    values = np.arange(100, dtype=float)
    values[39] = values[40] = values[38]  # positions 39, 40, 41
    t = quintile_targets(_returns(values))
    assert t.iloc[38].tolist() == pytest.approx([0, 2 / 3, 1 / 3, 0, 0])
    assert (t.sum(axis=1).round(12) == 1).all()


def test_tie_inside_a_quintile_is_one_hot():
    values = np.arange(100, dtype=float)
    values[5] = values[4]
    assert quintile_targets(_returns(values)).iloc[5].tolist() == [1, 0, 0, 0, 0]


def test_rps_hand_computed():
    returns = _returns(np.arange(100))
    targets = quintile_targets(returns)
    assert rps(targets, returns) == 0  # perfect forecast
    uniform = pd.DataFrame(0.2, index=returns.index, columns=RANK_COLUMNS)
    assert rps(uniform, returns) == pytest.approx(0.16)
    # One asset in quintile 1 forecast as certain quintile 5: cumulative diffs 1,1,1,1,0.
    wrong = targets.copy()
    wrong.iloc[0] = [0, 0, 0, 0, 1]
    assert rps_per_asset(wrong, targets).iloc[0] == pytest.approx(4 / 5)


def test_official_thresholds_require_100_assets():
    with pytest.raises(ValueError, match="100 assets"):
        quintile_targets(_returns(np.arange(99)))
    t = quintile_targets(_returns(np.arange(99)), n_assets_rule="proportional")
    assert (t.sum(axis=1) == 1).all()


def test_ir_hand_computed():
    dates = pd.bdate_range("2022-01-03", periods=4)
    wide = pd.DataFrame({"A": [100, 110, 99, 99], "B": [50, 50, 55, 44]}, index=dates, dtype=float)
    lr = portfolio_log_returns(wide, pd.Series({"A": 0.5, "B": -0.5}))
    expected = np.log1p([0.5 * 0.1, 0.5 * -0.1 - 0.5 * 0.1, -0.5 * -0.2])
    np.testing.assert_allclose(lr.to_numpy(), expected)
    assert information_ratio(lr) == pytest.approx(expected.sum() / expected.std(ddof=1))


def test_ir_zero_variance():
    lr = pd.Series([0.0, 0.0, 0.0])
    assert np.isnan(information_ratio(lr))
    assert information_ratio(lr, zero_variance=1.0) == 1.0


# ---------------------------------------------------------------------------- anti-leakage


def test_period_prices_ignore_data_after_end_date(assets, calendar):
    c = calendar.iloc[5]
    before = period_prices(assets, c.base_date, c.end_date)
    tampered = assets.copy()
    future = tampered["date"] > c.end_date
    tampered.loc[future, "price"] *= 1000
    pd.testing.assert_frame_equal(before, period_prices(tampered, c.base_date, c.end_date))


def test_delisted_asset_held_at_last_price(assets, calendar):
    c = calendar.set_index("sheet").loc["Month11"]
    wide = period_prices(assets, c.base_date, c.end_date)
    assert wide.shape[1] == 100
    last = assets.loc[assets["symbol"] == "DRE", "price"].iloc[-1]
    assert (wide["DRE"] == last).all()
    assert period_returns(wide)["DRE"] == 0


def test_period_bounds_must_be_trading_days(assets):
    with pytest.raises(ValueError):
        period_prices(assets, "2022-02-05", "2022-03-04")  # Saturday
