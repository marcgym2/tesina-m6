"""wound-ignite's frozen final configuration on periods 1 and 2 (issue #19, D8).

    uv sync --project vendor/wound-ignite
    uv run python experiments/wound_ignite/run.py [config.toml]

Writes results/wound_ignite/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per period.
- summary.csv: mean RPS and pooled IR per phase (gross and net).
- forecasts.parquet: quintile probabilities and weights per period and asset.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import eodhd, m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.external import PythonScriptModel

HERE = Path(__file__).resolve().parent
VENDOR = m6.REPO_ROOT / "vendor" / "wound-ignite"


def main(config_path: Path) -> None:
    config = load_config(config_path)
    data = config["data"]
    if not data["eodhd"]:
        sys.exit("config [data] eodhd is empty: the price snapshot comes from #12")
    prices_by_phase = eodhd.phase_prices(data["eodhd"], data["m6_snapshot"])
    assets = sorted(m6.load_template()["ID"])
    end = eodhd.snapshot(data["eodhd"])["cutoff_end"]

    ev = config["evaluation"]
    zero_variance = np.nan if ev["zero_variance"] == "nan" else float(ev["zero_variance"])
    spec = config["model"]
    model = PythonScriptModel(
        "wound_ignite", VENDOR, args=["--seed", str(spec["seed"])], decisions=spec["decisions"]
    )
    out = prepare_run("wound_ignite", config_path)
    periods, summaries, forecasts = [], [], []
    for phase, policy in ev["policy"].items():
        prices = prices_by_phase[phase]
        calendar = resolve(m6_calendar(end), prices["date"].unique())
        subset = calendar[calendar["phase"] == phase]
        result = run(model, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
        tag = {"model": model.name, "phase": phase}
        periods.append(result.periods.assign(**tag))
        summaries.append({**result.summary(zero_variance), "phase": phase})
        for label, f in result.forecasts.items():
            forecasts.append(f.probs.assign(weight=f.weights, label=label, **tag))
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config.toml")
