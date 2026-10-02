"""Quality report of the price snapshots (issue #13).

    uv run python experiments/data_quality/run.py [config.toml]

Writes results/data_quality/<date>_<commit>/:
- coverage.csv, gaps.csv, ohlc.csv, splits.csv, jumps.csv, stale.csv: findings of each
  check on the EODHD snapshot (tesina.data.quality).
- vs_official_daily.csv, vs_official_periods.csv: EODHD against the official M6 prices
  on period 1 (daily returns, period returns and quintile assignment).
- vs_yahoo_daily.csv, vs_yahoo_periods.csv: EODHD against Yahoo on period 2 (if a Yahoo
  snapshot is configured).
- report.md: counts and the flagged rows, to resolve or document each finding.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from tesina.data import eodhd, m6, quality
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.universe import DELISTINGS

HERE = Path(__file__).resolve().parent


def load_yahoo(downloaded: str) -> pd.DataFrame:
    snap = [s for s in m6.manifest()["snapshots"] if s["name"] == "yahoo"]
    snap = [s for s in snap if s["downloaded"] == downloaded]
    if not snap:
        raise FileNotFoundError(f"no yahoo snapshot for {downloaded} in the manifest")
    df = pd.read_parquet(m6.REPO_ROOT / snap[0]["files"][0]["path"])
    return df.rename(columns={"adjusted_close": "price"})[["symbol", "date", "price"]]


def markdown(frame: pd.DataFrame) -> str:
    cells = frame.astype(object).where(frame.notna(), "")
    rows = [list(frame.columns), ["---"] * frame.shape[1], *cells.astype(str).to_numpy().tolist()]
    return "\n".join("| " + " | ".join(map(str, r)) + " |" for r in rows)


def section(title: str, frame: pd.DataFrame, limit: int = 30) -> str:
    if frame.empty:
        return f"## {title}\n\nSin hallazgos.\n"
    shown = markdown(frame.head(limit).round(4))
    more = f"\n\n({len(frame) - limit} filas más en el CSV)" if len(frame) > limit else ""
    return f"## {title} ({len(frame)})\n\n{shown}{more}\n"


def main(config_path: Path) -> None:
    config = load_config(config_path)
    data, checks = config["data"], config["checks"]
    if not data["eodhd"]:
        sys.exit("config [data] eodhd is empty: the price snapshot comes from #12")
    raw = eodhd.load_raw(data["eodhd"])
    snap = eodhd.snapshot(data["eodhd"])
    expected = sorted(m6.load_template()["ID"]) + ["VIXY", "PLD", "SW"]
    out = prepare_run("data_quality", config_path)

    calendars = quality.reference_calendars(raw)
    findings = {
        "coverage": quality.coverage(
            raw, expected, checks["expected_start"], snap["cutoff_end"], DELISTINGS
        ),
        "gaps": quality.gaps(raw, calendars),
        "ohlc": quality.ohlc_problems(raw),
        "splits": quality.splits(raw),
        "jumps": quality.jumps(raw, checks["jump_threshold"]),
        "stale": quality.stale_runs(raw, checks["stale_min_run"]),
    }
    for name, frame in findings.items():
        frame.to_csv(out / f"{name}.csv", index=False)

    prices = eodhd.load_prices(data["eodhd"])
    official = m6.load_assets(data["m6_snapshot"])
    cal1 = resolve(m6_calendar(official["date"].max()), official["date"].unique())
    daily1, periods1 = quality.compare_sources(
        official, prices, cal1[cal1["phase"] == "period1"], checks["diff_bp"]
    )
    daily1.to_csv(out / "vs_official_daily.csv", index=False)
    periods1.to_csv(out / "vs_official_periods.csv", index=False)
    comparisons = {
        "EODHD vs precios oficiales del M6 (periodo 1), por activo": daily1,
        "EODHD vs precios oficiales del M6 (periodo 1), por periodo": periods1,
    }
    if data["yahoo"]:
        yahoo = load_yahoo(data["yahoo"])
        cal2 = resolve(m6_calendar(snap["cutoff_end"]), prices["date"].unique())
        daily2, periods2 = quality.compare_sources(
            prices, yahoo, cal2[cal2["phase"] == "period2"], checks["diff_bp"]
        )
        daily2.to_csv(out / "vs_yahoo_daily.csv", index=False)
        periods2.to_csv(out / "vs_yahoo_periods.csv", index=False)
        comparisons["EODHD vs Yahoo (periodo 2), por activo"] = daily2
        comparisons["EODHD vs Yahoo (periodo 2), por periodo"] = periods2

    coverage = findings["coverage"]
    flagged = coverage[coverage["flag"].fillna("") != ""]
    worst = {k: v.sort_values(v.columns[-1], ascending=False) for k, v in comparisons.items()}
    parts = [
        f"# Calidad de datos: EODHD {data['eodhd']}\n",
        f"Corte del periodo 2: {snap['cutoff_period']} ({snap['cutoff_end']}).\n",
        section("Cobertura con alguna marca", flagged),
        section("Huecos frente al calendario de la bolsa", findings["gaps"]),
        section("Problemas OHLC", findings["ohlc"]),
        section("Splits detectados (adjusted: el ajuste los absorbió)", findings["splits"]),
        section("Saltos del precio ajustado", findings["jumps"]),
        section("Rachas de precio ajustado constante", findings["stale"]),
        *(section(title, frame) for title, frame in worst.items()),
    ]
    (out / "report.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config.toml")
