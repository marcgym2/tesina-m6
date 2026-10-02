"""Helpers shared by experiments/<name>/run.py (reproducibility rules in CLAUDE.md)."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import tomllib
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "results"


def load_config(config_path: Path) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def prepare_run(name: str, config_path: Path) -> Path:
    """Create ``results/<name>/<date>_<commit>/`` with the config and run metadata.

    Refuses to overwrite an existing run directory: previous results are never
    rewritten. Records whether the working tree had uncommitted changes.
    """
    commit = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    out = RESULTS / name / f"{day}_{commit[:7]}{'-dirty' if dirty else ''}"
    if out.exists():
        raise FileExistsError(f"{out} exists; results are never overwritten")
    out.mkdir(parents=True)
    shutil.copy(config_path, out / "config.toml")
    info = {
        "experiment": name,
        "commit": commit,
        "dirty": dirty,
        "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "packages": {p: metadata.version(p) for p in ("numpy", "pandas", "pyarrow", "lightgbm")},
    }
    (out / "run_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return out
