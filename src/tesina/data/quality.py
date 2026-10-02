"""Data quality checks for the price snapshots (issue #13).

Every check returns a DataFrame of findings (empty = nothing found), so a report can
list them and decide, case by case, whether each one is fixed or documented.

Input frames are long format. ``raw`` is the EODHD snapshot as stored (``symbol``,
``date``, ``open``, ``high``, ``low``, ``close``, ``adjusted_close``, ``volume``);
comparisons use ``symbol``, ``date``, ``price``.

- ``coverage``: first and last date and rows per symbol, against the expected start,
  the cutoff and the delisting dates.
- ``gaps``: runs of missing trading days inside each series, against a reference
  calendar (the dates of the series' own exchange, from the other symbols).
- ``ohlc_problems``: rows that break basic price identities.
- ``splits``: days where ``close`` moves by a split-like factor. An adjusted series
  that moves too means the split was not adjusted.
- ``jumps``: large daily moves of the adjusted price that are not explained by a
  detected split.
- ``stale_runs``: runs of identical adjusted prices (stale or forward-filled data).
- ``compare_sources``: two sources on their common dates, daily and per M6 period,
  including whether both put each asset in the same quintile.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets

SPLIT_FACTORS = np.array([2, 3, 4, 5, 8, 10, 20, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 8, 1 / 10, 1 / 20])
SPLIT_TOLERANCE = 0.03  # relative distance of the close ratio to a split factor


def exchange(symbol: str) -> str:
    return "LSE" if symbol.endswith(".L") else "US"


def reference_calendars(raw: pd.DataFrame, min_share: float = 0.5) -> dict[str, pd.DatetimeIndex]:
    """Trading days of each exchange: dates on which at least ``min_share`` of the
    exchange's symbols that were already listed have a price."""
    calendars = {}
    for ex, group in raw.groupby(raw["symbol"].map(exchange)):
        present = group.pivot_table(index="date", columns="symbol", values="close", aggfunc="size")
        listed = present.notna().cummax()  # listed from its first price on
        share = present.notna().sum(axis=1) / listed.sum(axis=1)
        calendars[ex] = pd.DatetimeIndex(share.index[share >= min_share]).sort_values()
    return calendars


def coverage(
    raw: pd.DataFrame,
    expected: list[str],
    start,
    cutoff_end,
    delistings: dict[str, pd.Timestamp],
    tolerance_days: int = 7,
) -> pd.DataFrame:
    """One row per expected symbol with its range and the flags that apply."""
    start, cutoff_end = pd.Timestamp(start), pd.Timestamp(cutoff_end)
    stats = raw.groupby("symbol")["date"].agg(first="min", last="max", rows="size")
    rows = []
    for symbol in expected:
        if symbol not in stats.index:
            rows.append({"symbol": symbol, "rows": 0, "flag": "missing"})
            continue
        s = stats.loc[symbol]
        flags = []
        if s["first"] > start + pd.Timedelta(days=tolerance_days):
            flags.append("starts_late")  # listed later, or history cut (check by hand)
        if symbol in delistings:
            if abs((s["last"] - delistings[symbol]).days) > tolerance_days:
                flags.append("last_date_differs_from_delisting")
        elif s["last"] < cutoff_end - pd.Timedelta(days=tolerance_days):
            flags.append("ends_before_cutoff")
        rows.append(
            {
                "symbol": symbol,
                "first": s["first"].date(),
                "last": s["last"].date(),
                "rows": int(s["rows"]),
                "flag": ";".join(flags),
            }
        )
    return pd.DataFrame(rows)


def gaps(raw: pd.DataFrame, calendars: dict, min_days: int = 1) -> pd.DataFrame:
    """Runs of at least ``min_days`` exchange trading days without a price, inside each
    symbol's own first-to-last range."""
    rows = []
    for symbol, group in raw.groupby("symbol"):
        calendar = calendars[exchange(symbol)]
        dates = pd.DatetimeIndex(group["date"]).sort_values()
        span = calendar[(calendar >= dates[0]) & (calendar <= dates[-1])]
        missing = span.difference(dates)
        if missing.empty:
            continue
        position = span.get_indexer(missing)
        run_id = np.cumsum(np.diff(position, prepend=position[0] - 2) != 1)
        for _, run in pd.Series(missing, index=run_id).groupby(level=0):
            if len(run) >= min_days:
                rows.append(
                    {
                        "symbol": symbol,
                        "from": run.iloc[0].date(),
                        "to": run.iloc[-1].date(),
                        "days": len(run),
                    }
                )
    return pd.DataFrame(rows, columns=["symbol", "from", "to", "days"])


def ohlc_problems(raw: pd.DataFrame) -> pd.DataFrame:
    tol = 1e-9
    checks = {
        "nonpositive_price": (raw[["open", "high", "low", "close", "adjusted_close"]] <= 0).any(
            axis=1
        ),
        "missing_value": raw[["close", "adjusted_close"]].isna().any(axis=1),
        "high_below_low": raw["high"] < raw["low"] - tol,
        "close_outside_range": (raw["close"] > raw["high"] + tol)
        | (raw["close"] < raw["low"] - tol),
        "negative_volume": raw["volume"] < 0,
        "duplicated_date": raw.duplicated(["symbol", "date"], keep=False),
    }
    found = [raw.loc[m, ["symbol", "date"]].assign(problem=name) for name, m in checks.items()]
    return pd.concat(found, ignore_index=True)


def _daily(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.sort_values(["symbol", "date"])
    g = raw.groupby("symbol")
    return raw.assign(
        close_ratio=raw["close"] / g["close"].shift(1),
        adjusted_ratio=raw["adjusted_close"] / g["adjusted_close"].shift(1),
    ).dropna(subset=["close_ratio"])


def _nearest_factor(ratio: pd.Series) -> tuple[pd.Series, pd.Series]:
    distance = np.abs(ratio.to_numpy()[:, None] / SPLIT_FACTORS[None, :] - 1)
    best = distance.argmin(axis=1)
    return pd.Series(SPLIT_FACTORS[best], index=ratio.index), pd.Series(
        distance[np.arange(len(ratio)), best], index=ratio.index
    )


def splits(raw: pd.DataFrame) -> pd.DataFrame:
    """Split-like moves of ``close``; ``adjusted`` says whether the adjusted price
    absorbed them (its own move is far from the factor)."""
    d = _daily(raw)
    factor, distance = _nearest_factor(d["close_ratio"])
    hit = distance < SPLIT_TOLERANCE
    out = d.loc[hit, ["symbol", "date", "close_ratio", "adjusted_ratio"]].assign(factor=factor[hit])
    _, adj_distance = _nearest_factor(out["adjusted_ratio"])
    return out.assign(adjusted=adj_distance >= SPLIT_TOLERANCE).reset_index(drop=True)


def jumps(raw: pd.DataFrame, threshold: float = 0.25) -> pd.DataFrame:
    """Days with |log return of the adjusted price| above ``threshold``."""
    d = _daily(raw)
    logret = np.log(d["adjusted_ratio"])
    big = logret.abs() > threshold
    return (
        d.loc[big, ["symbol", "date", "adjusted_ratio", "close_ratio"]]
        .assign(log_return=logret[big])
        .reset_index(drop=True)
    )


def stale_runs(raw: pd.DataFrame, min_run: int = 5) -> pd.DataFrame:
    """Runs of at least ``min_run`` consecutive rows with the same adjusted price."""
    rows = []
    for symbol, group in raw.sort_values("date").groupby("symbol"):
        price = group["adjusted_close"].to_numpy()
        dates = group["date"].to_numpy()
        change = np.r_[True, price[1:] != price[:-1]]
        run_id = np.cumsum(change)
        for rid in np.unique(run_id):
            idx = np.flatnonzero(run_id == rid)
            if len(idx) >= min_run:
                rows.append(
                    {
                        "symbol": symbol,
                        "from": pd.Timestamp(dates[idx[0]]).date(),
                        "to": pd.Timestamp(dates[idx[-1]]).date(),
                        "rows": len(idx),
                        "price": float(price[idx[0]]),
                    }
                )
    return pd.DataFrame(rows, columns=["symbol", "from", "to", "rows", "price"])


def compare_sources(
    a: pd.DataFrame, b: pd.DataFrame, calendar: pd.DataFrame | None = None, bp: float = 10.0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare two sources (``symbol``, ``date``, ``price``) on their common dates.

    Returns ``(daily, periods)``. ``daily`` has one row per symbol: the median and
    maximum absolute difference of daily simple returns (basis points) and the share of
    days differing by more than ``bp``. ``periods`` (if a resolved M6 ``calendar`` with
    ``base_date``/``end_date`` is given) has one row per period: the largest difference
    in period returns and the share of assets placed in a different quintile.
    """
    wa = a.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    wb = b.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
    symbols = wa.columns.intersection(wb.columns)
    dates = wa.index.intersection(wb.index)
    wa, wb = wa.loc[dates, symbols].sort_index(), wb.loc[dates, symbols].sort_index()
    diff = (wa.pct_change(fill_method=None) - wb.pct_change(fill_method=None)).abs() * 1e4
    daily = (
        pd.DataFrame(
            {
                "days": diff.notna().sum(),
                "median_abs_diff_bp": diff.median(),
                "max_abs_diff_bp": diff.max(),
                "share_days_over_bp": (diff > bp).sum() / diff.notna().sum(),
            }
        )
        .rename_axis("symbol")
        .reset_index()
    )

    periods = pd.DataFrame()
    if calendar is not None:
        rows = []
        long_a = wa.reset_index().melt(id_vars="date", value_name="price").dropna()
        long_b = wb.reset_index().melt(id_vars="date", value_name="price").dropna()
        for period in calendar.itertuples():
            try:
                ra = period_returns(period_prices(long_a, period.base_date, period.end_date))
                rb = period_returns(period_prices(long_b, period.base_date, period.end_date))
            except ValueError:
                continue  # boundary dates missing in the common dates
            common = ra.dropna().index.intersection(rb.dropna().index)
            ra, rb = ra[common], rb[common]
            qa = quintile_targets(ra, "proportional").to_numpy().argmax(axis=1)
            qb = quintile_targets(rb, "proportional").to_numpy().argmax(axis=1)
            rows.append(
                {
                    "label": period.label,
                    "assets": len(common),
                    "max_abs_return_diff": float((ra - rb).abs().max()),
                    "share_different_quintile": float((qa != qb).mean()),
                }
            )
        periods = pd.DataFrame(rows)
    return daily, periods
