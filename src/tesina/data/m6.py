"""Typed loaders for the frozen official M6 files (see data/raw/m6_official/README.md).

The raw snapshot stores every CSV column as a string; typing happens here so the
raw files stay a lossless copy of upstream.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "data" / "manifest.json"
SNAPSHOT = "m6_official"

RANK_COLUMNS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]
# Order of the evaluation months in period 1 ("Trial run" is the pilot).
EVALUATIONS = ["Trial run"] + [
    f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} Submission"
    for n in range(1, 13)
]


@cache
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def snapshot_files(downloaded: str | None = None) -> dict[str, dict]:
    """Manifest entries of the M6 snapshot, keyed by stored name (e.g. ``"assets_m6"``).

    Uses the most recent snapshot unless ``downloaded`` (YYYY-MM-DD) is given.
    """
    snaps = [s for s in manifest()["snapshots"] if s["name"] == SNAPSHOT]
    if downloaded:
        snaps = [s for s in snaps if s["downloaded"] == downloaded]
    if not snaps:
        raise FileNotFoundError(f"no {SNAPSHOT} snapshot in {MANIFEST}")
    snap = max(snaps, key=lambda s: s["downloaded"])
    return {Path(f["path"]).stem.rsplit("_", 1)[0]: f for f in snap["files"]}


def path(name: str, downloaded: str | None = None) -> Path:
    return REPO_ROOT / snapshot_files(downloaded)[name]["path"]


def verify(downloaded: str | None = None) -> None:
    """Raise if any stored file does not match its manifest SHA-256."""
    for name, entry in snapshot_files(downloaded).items():
        digest = hashlib.sha256((REPO_ROOT / entry["path"]).read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"{name}: sha256 mismatch ({entry['path']})")


def load_assets(downloaded: str | None = None) -> pd.DataFrame:
    """Daily adjusted close prices: ``symbol`` (str), ``date`` (datetime64), ``price`` (float)."""
    df = pd.read_parquet(path("assets_m6", downloaded))
    return pd.DataFrame(
        {
            "symbol": df["symbol"].astype(str),
            "date": pd.to_datetime(df["date"], format="%Y/%m/%d"),
            "price": df["price"].astype(float),
        }
    )


def load_submissions(downloaded: str | None = None) -> pd.DataFrame:
    """Team submissions of period 1 with numeric columns typed.

    ``Evaluation`` is the month the submission was scored in; when a team did not
    resubmit, its previous submission is carried forward (``Submission`` differs).
    """
    df = pd.read_parquet(path("submissions", downloaded))
    out = df[["Team", "Submission", "Evaluation", "Symbol"]].astype(str).copy()
    for col in ["Decision", *RANK_COLUMNS]:
        out[col] = df[col].astype(float)
    out["IsActive"] = df["IsActive"].astype(int)
    for col in ["RpsHashCode", "IrHashCode"]:
        out[col] = pd.to_numeric(df[col].replace("", None)).astype("Int64")
    return out


def load_template(downloaded: str | None = None) -> pd.DataFrame:
    """Official submission template: uniform probabilities and equal weights (0.01)."""
    df = pd.read_parquet(path("template", downloaded))
    out = df[["ID"]].astype(str).copy()
    for col in [*RANK_COLUMNS, "Decision"]:
        out[col] = df[col].astype(float)
    return out
