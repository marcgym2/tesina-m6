"""Point-in-time asset universe (rule 5 of CLAUDE.md).

Policies:

- ``"official"``: every M6 asset with a price on or before the origin. Delisted
  assets stay in the universe and are held at their last price, as the M6 did
  (period 1; sensitivity analysis C of issue #11).
- ``"d2"``: decision D2 (docs/decisions.md, issue #11). An asset is excluded from
  every period whose origin is on or after its delisting date. A delisting is public
  on the day it happens, so this uses no information from after the origin.
"""

from __future__ import annotations

import pandas as pd

# Operational delisting dates (first origin from which the asset is excluded under D2).
DELISTINGS = {
    # Acquired by Prologis; last price in the official M6 data (data/raw/m6_official).
    "DRE": pd.Timestamp("2022-11-28"),
    # Merged into Smurfit WestRock (SW); delisted from the NYSE on 2024-07-05 (issue #11).
    "WRK": pd.Timestamp("2024-07-05"),
}
POLICIES = ("official", "d2")


def universe(history: pd.DataFrame, origin, policy: str = "official") -> list[str]:
    """Assets eligible for the period starting at ``origin`` (sorted symbols).

    ``history`` holds prices (``symbol``, ``date``, ``price``) up to ``origin``;
    later rows are ignored.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown universe policy {policy!r}")
    origin = pd.Timestamp(origin)
    known = set(history.loc[history["date"] <= origin, "symbol"])
    if policy == "d2":
        known -= {s for s, delisted in DELISTINGS.items() if delisted <= origin}
    return sorted(known)


def n_assets_rule(n_assets: int) -> str:
    """Quintile threshold rule: official for 100 assets, proportional otherwise (D2)."""
    return "official" if n_assets == 100 else "proportional"
