import pandas as pd
import pytest

from tesina.data import m6
from tesina.evaluation.calendar import cutoff, m6_calendar, resolve


@pytest.fixture(scope="module")
def calendar():
    return m6_calendar("2026-10-01")


def test_reproduces_official_period1_calendar(calendar):
    official = m6.load_period1_calendar()
    mine = calendar[calendar["phase"] != "period2"].reset_index(drop=True)
    assert mine["label"].tolist() == official["evaluation"].tolist()
    assert (mine["base"] == official["base_date"]).all()
    assert (mine["end"] == official["end_date"]).all()


def test_resolved_trading_days_match_official_data(calendar):
    dates = m6.load_assets()["date"].unique()
    official = m6.load_period1_calendar()
    resolved = resolve(calendar[calendar["phase"] != "period2"], dates)
    assert resolved["n_days"].tolist() == official["n_days"].tolist()
    assert (resolved["base_date"] == official["base_date"]).all()


def test_grid_is_contiguous_fridays(calendar):
    assert (calendar["base"].dt.dayofweek == 4).all()
    assert (calendar["end"].dt.dayofweek == 4).all()
    assert (calendar["start"].dt.dayofweek == 0).all()
    assert ((calendar["end"] - calendar["base"]).dt.days == 28).all()
    assert (calendar["base"].iloc[1:].to_numpy() == calendar["end"].iloc[:-1].to_numpy()).all()
    deadline = calendar["deadline"]
    assert (deadline.dt.dayofweek == 6).all() and (deadline.dt.hour == 18).all()
    assert ((calendar["start"] - deadline).dt.total_seconds() == 6 * 3600).all()


def test_period2_starts_right_after_the_competition(calendar):
    p2 = calendar[calendar["phase"] == "period2"]
    first = p2.iloc[0]
    assert (first["k"], first["label"]) == (13, "P2-01")
    assert first["base"] == pd.Timestamp("2023-02-03")  # end of the 12th submission
    assert first["end"] == pd.Timestamp("2023-03-03")


def test_holiday_on_a_boundary_moves_to_previous_trading_day(calendar):
    # Good Friday 2024-03-29 is a nominal boundary; NYSE and LSE were closed.
    days = pd.bdate_range("2024-02-01", "2024-05-31").drop(pd.Timestamp("2024-03-29"))
    window = calendar[(calendar["end"] >= "2024-03-01") & (calendar["end"] <= "2024-04-26")]
    resolved = resolve(window, days).set_index("end")
    before, after = resolved.loc["2024-03-29"], resolved.loc["2024-04-26"]
    assert before["end_date"] == pd.Timestamp("2024-03-28")
    assert after["base_date"] == pd.Timestamp("2024-03-28")
    assert (before["n_days"], after["n_days"]) == (19, 20)


def test_cutoff_is_last_complete_period():
    assert cutoff("2026-10-01")["end"] == pd.Timestamp("2026-09-11")
    assert cutoff("2026-09-12")["end"] == pd.Timestamp("2026-09-11")
    # On the end date itself the last close may not be final yet.
    assert cutoff("2026-09-11")["end"] == pd.Timestamp("2026-08-14")


def test_calendar_stops_at_until():
    assert m6_calendar("2022-03-03").empty
    assert len(m6_calendar("2022-03-04")) == 1
