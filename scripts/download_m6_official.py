"""Freeze the official M6 competition files into data/raw/ (issue #8).

    uv run python scripts/download_m6_official.py [--commit SHA] [--date YYYY-MM-DD]

Downloads from https://github.com/Mcompetitions/M6-methods at a pinned commit:

- ``assets_m6.csv``            daily adjusted close prices of the 100 M6 assets
- ``IJF paper/submissions.csv`` all team submissions (period 1)
- ``template.csv``             submission template (uniform benchmark)
- ``Evaluation - example.xlsx`` official worked example of RPS/IR (benchmark submission)
- ``IJF paper/summary_leaderboard.xlsx`` official per-team scores by month/quarter/total

CSV files are stored as parquet with every column kept as a string, so the
snapshot is lossless (typing happens in ``tesina.data.m6``); spreadsheets are
stored byte for byte. Files are written as ``data/raw/m6_official/<name>_<date>.<ext>``
and registered in ``data/manifest.json`` with the SHA-256 of both the upstream
file and the stored file. Existing snapshots are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "m6_official"
MANIFEST = REPO_ROOT / "data" / "manifest.json"

UPSTREAM = "Mcompetitions/M6-methods"
# HEAD of main on 2026-09-28 (last upstream push: 2024-10-02).
DEFAULT_COMMIT = "10c553f7a5ffbaf53971ca48ea982b2c0dd952ed"
GIT_SIZE_LIMIT = 50 * 1024 * 1024  # CLAUDE.md: snapshots < 50 MB go in git

# (upstream path, stored name)
FILES = [
    ("assets_m6.csv", "assets_m6"),
    ("IJF paper/submissions.csv", "submissions"),
    ("template.csv", "template"),
    ("Evaluation - example.xlsx", "evaluation_example"),
    ("IJF paper/summary_leaderboard.xlsx", "summary_leaderboard"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data: bytes) -> str:
    """SHA-1 git uses for a blob; lets anyone check the file against the upstream tree."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def fetch(commit: str, path: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{UPSTREAM}/{commit}/{urllib.parse.quote(path)}"
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def csv_to_parquet(data: bytes) -> bytes:
    df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow", compression="zstd")
    stored = buffer.getvalue()
    # Lossless check: every cell survives the round trip.
    back = pd.read_parquet(io.BytesIO(stored), engine="pyarrow")
    pd.testing.assert_frame_equal(df, back)
    return stored


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"snapshots": []}


def snapshot(commit: str, day: str) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for upstream_path, name in FILES:
        raw = fetch(commit, upstream_path)
        suffix = Path(upstream_path).suffix
        if suffix == ".csv":
            stored, ext, note = csv_to_parquet(raw), ".parquet", "CSV -> parquet, all columns str"
        else:
            stored, ext, note = raw, suffix, "verbatim"
        target = RAW_DIR / f"{name}_{day}{ext}"
        if target.exists():
            raise FileExistsError(f"{target} exists; snapshots are never overwritten")
        target.write_bytes(stored)
        entries.append(
            {
                "path": str(target.relative_to(REPO_ROOT)),
                "sha256": sha256(stored),
                "bytes": len(stored),
                "in_git": len(stored) < GIT_SIZE_LIMIT,
                "format": note,
                "upstream_path": upstream_path,
                "upstream_sha256": sha256(raw),
                "upstream_git_blob": git_blob_sha(raw),
                "upstream_bytes": len(raw),
            }
        )
        print(f"{target.relative_to(REPO_ROOT)}  {len(raw):>10} -> {len(stored):>10} bytes")
    return {
        "name": "m6_official",
        "downloaded": day,
        "source": f"https://github.com/{UPSTREAM}",
        "commit": commit,
        "license": "none declared upstream (see data/raw/m6_official/README.md)",
        "files": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit", default=DEFAULT_COMMIT)
    parser.add_argument("--date", default=date.today().isoformat(), help="download date tag")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    if any(
        s["name"] == "m6_official" and s["downloaded"] == args.date for s in manifest["snapshots"]
    ):
        print(f"m6_official snapshot for {args.date} already in manifest", file=sys.stderr)
        return 1
    manifest["snapshots"].append(snapshot(args.commit, args.date))
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {MANIFEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
