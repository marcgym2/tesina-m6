"""Freeze Yahoo Finance prices as an independent check of the EODHD snapshot (issue #13).

    uv sync --extra verify
    uv run python scripts/download_yahoo.py [--date YYYY-MM-DD] [--start 2007-01-01]
    uv run python scripts/download_yahoo.py --symbols IVV RE --out-dir /tmp/x --no-manifest

Yahoo is only a cross-check (issue #12, option A): the evaluation uses EODHD. Yahoo
drops delisted tickers, so DRE and WRK are absent (that is itself an example of a
provider's survivorship bias). RE is requested as EG, its ticker since 2023-07-10.

Stored as ``data/raw/yahoo/prices_<date>.parquet`` (``symbol`` as in the M6, ``ticker``,
``date``, ``close``, ``adjusted_close``, ``volume``), outside git because Yahoo's terms
forbid redistribution, and registered in ``data/manifest.json`` with its SHA-256 and
the symbols that came back empty. Snapshots are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "yahoo"
MANIFEST = REPO_ROOT / "data" / "manifest.json"
TICKERS = {"RE": "EG"}  # M6 symbol -> Yahoo ticker where they differ


def core_symbols() -> list[str]:
    path = REPO_ROOT / "scripts" / "download_eodhd.py"
    spec = importlib.util.spec_from_file_location("download_eodhd", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SYMBOLS


def download(symbols: list[str], start: str, end: str) -> tuple[pd.DataFrame, list[str]]:
    import yfinance as yf  # optional extra "verify"

    tickers = {s: TICKERS.get(s, s) for s in symbols}
    data = yf.download(
        list(tickers.values()),
        start=start,
        end=end,
        auto_adjust=False,
        actions=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    frames, empty = [], []
    for symbol, ticker in tickers.items():
        if ticker not in data.columns.get_level_values(0):
            empty.append(symbol)
            continue
        df = data[ticker].dropna(subset=["Close"])
        if df.empty:
            empty.append(symbol)
            continue
        frames.append(
            pd.DataFrame(
                {
                    "symbol": symbol,
                    "ticker": ticker,
                    "date": pd.DatetimeIndex(df.index).tz_localize(None).normalize(),
                    "close": df["Close"].to_numpy(dtype=float),
                    "adjusted_close": df["Adj Close"].to_numpy(dtype=float),
                    "volume": df["Volume"].to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True), empty


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", default=date.today().isoformat(), help="download date tag")
    parser.add_argument("--start", default="2007-01-01")
    parser.add_argument("--symbols", nargs="+", help="subset (testing)")
    parser.add_argument("--out-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--no-manifest", action="store_true")
    args = parser.parse_args(argv)

    symbols = args.symbols or core_symbols()
    target = args.out_dir / f"prices_{args.date}.parquet"
    if target.exists():
        raise SystemExit(f"{target} exists; snapshots are never overwritten")
    prices, empty = download(symbols, args.start, args.date)
    buffer = io.BytesIO()
    prices.to_parquet(buffer, index=False, compression="zstd")
    stored = buffer.getvalue()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stored)
    print(f"{target}: {prices['symbol'].nunique()} symbols, {len(prices)} rows; empty: {empty}")
    if args.no_manifest:
        return 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["snapshots"].append(
        {
            "name": "yahoo",
            "downloaded": args.date,
            "source": "Yahoo Finance via yfinance (cross-check only, issue #13)",
            "license": "Yahoo terms of use: redistribution forbidden; the file is not committed",
            "start": args.start,
            "empty_symbols": empty,
            "files": [
                {
                    "path": str(target.resolve().relative_to(REPO_ROOT)),
                    "sha256": hashlib.sha256(stored).hexdigest(),
                    "bytes": len(stored),
                    "in_git": False,
                    "format": "yfinance download (auto_adjust=False) -> parquet, long format",
                }
            ],
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {MANIFEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
