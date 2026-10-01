"""Calendar of M6 evaluation periods, extended beyond the competition (issue #14).

Rules, from the official sources available (the guidelines PDF is no longer online):

- Makridakis et al. (arXiv:2310.13357v1, section 2): each submission covers the next
  four weeks ("usually, the next 20 trading days"); consecutive periods do not
  overlap; the deadline is 18:00 GMT on the Sunday before the period starts.
- ``IJF paper/Baseline for evaluating the hypotheses.R``: period ends are Fridays
  four weeks apart and each start is ``end - 28`` days (the close the returns are
  measured from).
- ``Evaluation - example.xlsx``: the trial run starts from the close of 2022-02-04.

Hence a fixed grid of Fridays 28 days apart from 2022-02-04. Period 0 is the trial
run, 1-12 are the competition (period 1 of the thesis) and 13 onwards the extension
(period 2). Grid dates are nominal: ``resolve`` maps them to the last trading day on
or before each one, so a holiday on a boundary (e.g. Good Friday 2024-03-29) moves
the boundary to the previous trading day for both adjacent periods.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

ORIGIN = date(2022, 2, 4)
PERIOD_DAYS = 28
N_COMPETITION = 12  # periods 1-12 = M6 competition
DEADLINE_TIME = time(18, 0)  # GMT, Sunday before the period starts


def _label(k: int) -> str:
    if k == 0:
        return "Trial run"
    if k <= N_COMPETITION:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(k, "th")
        return f"{k}{suffix} Submission"  # as in submissions.Evaluation
    return f"P2-{k - N_COMPETITION:02d}"


def _phase(k: int) -> str:
    return "trial" if k == 0 else "period1" if k <= N_COMPETITION else "period2"


def m6_calendar(until: date | str) -> pd.DataFrame:
    """Every period whose nominal end is on or before ``until``.

    Columns: ``k``, ``label``, ``phase`` (trial / period1 / period2), ``base``
    (nominal Friday whose close starts the period), ``start`` (Monday), ``end``
    (nominal Friday, last day) and ``deadline`` (Sunday 18:00 GMT before ``start``).
    """
    until = pd.Timestamp(until).date()
    rows = []
    k = 0
    while True:
        base = ORIGIN + timedelta(days=PERIOD_DAYS * k)
        end = base + timedelta(days=PERIOD_DAYS)
        if end > until:
            break
        start = base + timedelta(days=3)
        deadline = datetime.combine(start - timedelta(days=1), DEADLINE_TIME)
        rows.append(
            {
                "k": k,
                "label": _label(k),
                "phase": _phase(k),
                "base": pd.Timestamp(base),
                "start": pd.Timestamp(start),
                "end": pd.Timestamp(end),
                "deadline": pd.Timestamp(deadline),
            }
        )
        k += 1
    return pd.DataFrame(rows)


def resolve(calendar: pd.DataFrame, trading_dates) -> pd.DataFrame:
    """Map nominal boundaries to trading days present in the data.

    Adds ``base_date`` and ``end_date`` (last trading day on or before ``base`` and
    ``end``) and ``n_days`` (trading days in ``(base_date, end_date]``). Eligible days
    follow the official code: dates with at least one price in the data.
    """
    days = pd.DatetimeIndex(sorted(set(pd.to_datetime(trading_dates))))
    out = calendar.copy()

    def last_on_or_before(ts):
        pos = days.searchsorted(ts, side="right") - 1
        if pos < 0:
            raise ValueError(f"no trading day on or before {ts.date()}")
        return days[pos]

    out["base_date"] = out["base"].map(last_on_or_before)
    out["end_date"] = out["end"].map(last_on_or_before)
    bounds = zip(out["base_date"], out["end_date"], strict=True)
    out["n_days"] = [int(((days > b) & (days <= e)).sum()) for b, e in bounds]
    return out


def cutoff(download_date: date | str) -> pd.Series:
    """Last complete period before ``download_date`` (decision D3, docs/decisions.md).

    A period is complete when its nominal end is strictly before the download date,
    so its last close is final when the data are downloaded.
    """
    download = pd.Timestamp(download_date).date()
    calendar = m6_calendar(download - timedelta(days=1))
    if calendar.empty:
        raise ValueError(f"no complete period before {download}")
    return calendar.iloc[-1]
