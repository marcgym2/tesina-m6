"""Freeze daily prices from EOD Historical Data into data/raw/eodhd/ (issue #12).

    uv run python scripts/download_eodhd.py [--date YYYY-MM-DD] [--start 2007-01-01]
    uv run python scripts/download_eodhd.py --group sebrad [--date ...]
    uv run python scripts/download_eodhd.py --symbols IVV IEFM.L --out-dir /tmp/x --no-manifest

Reads the API key from ``EODHD_API_KEY`` (environment or the repo's ``.env``, which git
ignores); the key is never printed or stored. One call per symbol.

Symbols (``SYMBOLS``): the 100 M6 assets plus auxiliary series that models or analyses
use as inputs but that are never evaluated:

- ``VIXY``: FinQBoost (#17) uses it in place of VXX.
- ``PLD`` and ``SW``: successors of DRE and WRK, needed by the survivorship step of the
  bias cascade (decision D6).

``--group sebrad`` downloads instead the extended universe of sebrad's method (#18,
``data/universes/sebrad_extended.csv``) into ``sebrad_<date>.parquet``; there a missing
symbol is recorded in the manifest but does not stop the save, as in sebrad's own code.

Stored as ``data/raw/eodhd/prices_<date>.parquet`` in long format: ``symbol`` (M6 code),
``ticker`` (EODHD code), ``date``, ``open``, ``high``, ``low``, ``close``,
``adjusted_close``, ``volume``, exactly as returned. The file is registered in
``data/manifest.json`` with its SHA-256, the cutoff of period 2 (decision D3) and, per
symbol, the rows and date range received. EODHD's terms forbid redistribution, so the
file stays out of git (``in_git: false``) whatever its size. A snapshot is never
overwritten. A full download refuses to start on the free plan, which silently cuts
every series to the last year, and writes nothing if any symbol is missing or comes
with an API warning.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "eodhd"
MANIFEST = REPO_ROOT / "data" / "manifest.json"
API = "https://eodhd.com/api"
COLUMNS = ["date", "open", "high", "low", "close", "adjusted_close", "volume"]

M6_ASSETS = [
    "ABBV", "ACN", "AEP", "AIZ", "ALLE", "AMAT", "AMP", "AMZN", "AVB", "AVY", "AXP", "BDX",
    "BF-B", "BMY", "BR", "CARR", "CDW", "CE", "CHTR", "CNC", "CNP", "COP", "CTAS", "CZR",
    "DG", "DPZ", "DRE", "DXC", "EWA", "EWC", "EWG", "EWH", "EWJ", "EWL", "EWQ", "EWT", "EWU",
    "EWY", "EWZ", "FTV", "GOOG", "GPC", "GSG", "HIG", "HIGH.L", "HST", "HYG", "IAU", "ICLN",
    "IEAA.L", "IEF", "IEFM.L", "IEMG", "IEUS", "IEVL.L", "IGF", "INDA", "IUMO.L", "IUVL.L",
    "IVV", "IWM", "IXN", "JPEA.L", "JPM", "KR", "LQD", "MCHI", "META", "MVEU.L", "OGN", "PG",
    "PPL", "PRU", "PYPL", "RE", "REET", "ROL", "ROST", "SEGA.L", "SHY", "SLV", "SPMV.L",
    "TLT", "UNH", "URI", "V", "VRSK", "VXX", "WRK", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
    "XLP", "XLU", "XLV", "XLY", "XOM",
]  # fmt: skip
AUXILIARY = ["VIXY", "PLD", "SW"]
SYMBOLS = M6_ASSETS + AUXILIARY
SEBRAD_LIST = REPO_ROOT / "data" / "universes" / "sebrad_extended.csv"


def group_symbols(group: str) -> list[str]:
    if group == "core":
        return SYMBOLS
    if group == "sebrad":
        return pd.read_csv(SEBRAD_LIST)["symbol"].tolist()
    raise SystemExit(f"unknown group {group!r}")


# Per group: file prefix, manifest name and whether any missing symbol aborts the save.
GROUPS = {
    "core": ("prices", "eodhd", True),
    "sebrad": ("sebrad", "eodhd_sebrad", False),
}

# EODHD codes that do not follow the default rule (``X.L`` -> ``X.LSE``, else ``X.US``).
# RE changed its ticker to EG on 2023-07-10 (decision D2); whether EODHD keeps the
# pre-2023 history under EG is checked against the official M6 prices in #13.
TICKER_OVERRIDES = {"RE": "EG.US"}


def ticker(symbol: str) -> str:
    if symbol in TICKER_OVERRIDES:
        return TICKER_OVERRIDES[symbol]
    if symbol.endswith(".L"):
        return symbol[:-2] + ".LSE"
    return symbol + ".US"


def api_key() -> str:
    key = os.environ.get("EODHD_API_KEY")
    env = REPO_ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("EODHD_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("EODHD_API_KEY not set (environment or .env)")
    return key


def get_json(path: str, key: str, retries: int = 3, **params):
    query = urllib.parse.urlencode({**params, "api_token": key, "fmt": "json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(f"{API}/{path}?{query}", timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            retriable = error.code == 429 or error.code >= 500
            if not retriable or attempt == retries - 1:
                body = error.read()[:200].decode(errors="replace").replace(key, "***")
                raise RuntimeError(f"HTTP {error.code} for {path}: {body}") from None
            time.sleep(2**attempt * 5)
    raise AssertionError("unreachable")


def parse(symbol: str, payload) -> tuple[pd.DataFrame, list[str]]:
    """Rows of one symbol and any warnings EODHD returned in their place."""
    if not isinstance(payload, list):
        return pd.DataFrame(columns=COLUMNS), [f"unexpected payload: {str(payload)[:200]}"]
    rows = [r for r in payload if isinstance(r, dict) and "date" in r]
    warnings = [
        str(r.get("warning", r)) for r in payload if not (isinstance(r, dict) and "date" in r)
    ]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.insert(0, "ticker", ticker(symbol))
    df.insert(0, "symbol", symbol)
    return df, warnings


def check(df: pd.DataFrame) -> list[str]:
    problems = []
    if df.empty:
        return ["no rows"]
    if df["date"].duplicated().any():
        problems.append("duplicated dates")
    if not df["date"].is_monotonic_increasing:
        problems.append("dates not sorted")
    if (pd.to_numeric(df["adjusted_close"], errors="coerce") <= 0).any():
        problems.append("non-positive adjusted_close")
    return problems


def to_parquet(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow", compression="zstd")
    return buffer.getvalue()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"snapshots": []}


def download(symbols: list[str], start: str, end: str, key: str):
    frames, report = [], []
    for symbol in symbols:
        df, warnings = parse(
            symbol, get_json(f"eod/{ticker(symbol)}", key, **{"from": start, "to": end})
        )
        problems = check(df)
        report.append(
            {
                "symbol": symbol,
                "ticker": ticker(symbol),
                "rows": len(df),
                "first": df["date"].iloc[0] if len(df) else None,
                "last": df["date"].iloc[-1] if len(df) else None,
                "warnings": warnings,
                "problems": problems,
            }
        )
        status = "ok" if not (warnings or problems) else "; ".join(warnings + problems)
        print(f"{symbol:8} {ticker(symbol):10} {len(df):>6} rows  {status}")
        frames.append(df)
    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"])
    for col in COLUMNS[1:]:
        prices[col] = pd.to_numeric(prices[col])
    return prices, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", default=date.today().isoformat(), help="download date tag")
    parser.add_argument("--start", default="2007-01-01")
    parser.add_argument("--group", choices=sorted(GROUPS), default="core")
    parser.add_argument("--symbols", nargs="+", help="subset of the group (testing)")
    parser.add_argument("--out-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--no-manifest", action="store_true", help="do not register (testing)")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from tesina.evaluation.calendar import cutoff

    prefix, name, strict = GROUPS[args.group]
    every = group_symbols(args.group)
    symbols = args.symbols or every
    unknown = sorted(set(symbols) - set(every))
    if unknown:
        raise SystemExit(f"unknown symbols for group {args.group}: {unknown}")
    full = symbols == every and not args.no_manifest
    target = args.out_dir / f"{prefix}_{args.date}.parquet"
    if target.exists():
        raise SystemExit(f"{target} exists; snapshots are never overwritten")
    manifest = load_manifest()
    if full and any(
        s["name"] == name and s["downloaded"] == args.date for s in manifest["snapshots"]
    ):
        raise SystemExit(f"{name} snapshot for {args.date} already in manifest")

    period = cutoff(args.date)
    key = api_key()
    plan = get_json("user", key).get("subscriptionType", "unknown")
    if full and plan == "free":
        # The free plan silently truncates every series to the last year.
        raise SystemExit("free EODHD plan: history is limited to one year; not downloading")
    prices, report = download(symbols, args.start, args.date, key)
    failed = [r["symbol"] for r in report if r["warnings"] or r["problems"]]
    if failed:
        print(f"{len(failed)} symbols with warnings or problems: {failed}")
    if full and strict and failed:
        print("not saved")
        return 1

    stored = to_parquet(prices)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stored)
    print(f"{target}  {len(prices)} rows, {len(stored)} bytes")
    if args.no_manifest:
        return 0
    path = target.resolve().relative_to(REPO_ROOT)
    manifest["snapshots"].append(
        {
            "name": name,
            "downloaded": args.date,
            "source": API,
            "license": "EODHD terms of use: storage and analysis allowed, redistribution "
            "forbidden; the file is not committed",
            "plan": plan,
            "start": args.start,
            "cutoff_period": period["label"],
            "cutoff_end": period["end"].date().isoformat(),
            "files": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(stored).hexdigest(),
                    "bytes": len(stored),
                    "in_git": False,
                    "format": "EODHD /eod JSON -> parquet, long format, values as returned",
                }
            ],
            "symbols": report,
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    end = period["end"].date()
    print(f"updated {MANIFEST.relative_to(REPO_ROOT)}; cutoff {period['label']} ({end})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
