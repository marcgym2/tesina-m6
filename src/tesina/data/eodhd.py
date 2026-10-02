"""Loaders for the EODHD price snapshot (issue #12) and the price input of each phase.

The snapshot (``scripts/download_eodhd.py``) holds daily prices since 2007 for the M6
assets and a few auxiliary series. It is not in git (EODHD forbids redistribution);
``data/manifest.json`` keeps its SHA-256, so a copy can be checked.

Price inputs (chapter 6, section "Fuentes"):

- **Period 2**: EODHD adjusted closes up to the cutoff (decision D3), both as model
  history and for scoring.
- **Period 1**: the official M6 prices, which the competition was scored with, from
  their first date (2022-01-31). Earlier history comes from EODHD, rescaled per asset
  by a constant so that it meets the official level on that first date. A constant
  factor leaves every return unchanged, so the splice adds no artificial jump; it only
  uses prices of 2022-01-31, before the first forecast origin of period 1.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from tesina.data import m6

SNAPSHOT = "eodhd"


def snapshot(downloaded: str | None = None) -> dict:
    """Manifest entry of the EODHD snapshot (the most recent unless ``downloaded``)."""
    snaps = [s for s in m6.manifest()["snapshots"] if s["name"] == SNAPSHOT]
    if downloaded:
        snaps = [s for s in snaps if s["downloaded"] == downloaded]
    if not snaps:
        raise FileNotFoundError(f"no {SNAPSHOT} snapshot in {m6.MANIFEST} (issue #12)")
    return max(snaps, key=lambda s: s["downloaded"])


def load_raw(downloaded: str | None = None) -> pd.DataFrame:
    """The snapshot as stored, after checking its SHA-256 against the manifest."""
    entry = snapshot(downloaded)["files"][0]
    file = m6.REPO_ROOT / entry["path"]
    if not file.exists():
        raise FileNotFoundError(f"{file} is not in git; download it with scripts/download_eodhd.py")
    data = file.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError(f"{file}: sha256 mismatch")
    return pd.read_parquet(file)


def load_prices(downloaded: str | None = None) -> pd.DataFrame:
    """Adjusted closes up to the cutoff: ``symbol`` (M6 code), ``date``, ``price``."""
    raw = load_raw(downloaded)
    end = pd.Timestamp(snapshot(downloaded)["cutoff_end"])
    out = raw.loc[raw["date"] <= end, ["symbol", "date", "adjusted_close"]]
    return out.rename(columns={"adjusted_close": "price"}).reset_index(drop=True)


def splice(history: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Official prices from their first date, preceded by rescaled ``history``.

    Both frames have ``symbol``, ``date`` and ``price``. For each asset in ``official``,
    ``history`` before the asset's first official date is multiplied by the ratio between the
    official price and the history price on that date (or, if the history lacks it,
    on its last date before). Assets only in ``history`` (auxiliary series) keep
    their prices, but within and after the official window only on official trading
    days, so they cannot add days to the calendar or the scoring of period 1. Assets
    without history keep only their official prices.
    """
    parts = [official[["symbol", "date", "price"]]]
    official_dates = set(official["date"])
    official_start = official["date"].min()
    for symbol, hist in history.groupby("symbol", sort=False):
        hist = hist.sort_values("date")
        own = official[official["symbol"] == symbol]
        if own.empty:
            keep = (hist["date"] < official_start) | hist["date"].isin(official_dates)
            parts.append(hist.loc[keep, ["symbol", "date", "price"]])
            continue
        first = own["date"].min()
        anchor = hist[hist["date"] <= first]
        if anchor.empty:
            continue
        ratio = own.loc[own["date"] == first, "price"].iloc[0] / anchor["price"].iloc[-1]
        before = hist[hist["date"] < first]
        parts.append(before.assign(price=before["price"] * ratio)[["symbol", "date", "price"]])
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["symbol", "date"], ignore_index=True)


def phase_prices(downloaded: str | None = None, m6_downloaded: str | None = None) -> dict:
    """Price input per phase: ``{"period1": ..., "period2": ...}`` (see module docstring)."""
    history = load_prices(downloaded)
    return {"period1": splice(history, m6.load_assets(m6_downloaded)), "period2": history}
