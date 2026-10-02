"""Simulation from covariances on periods 1 and 2 (issue #22).

    uv run python experiments/covsim/run.py [config.toml]

Writes results/covsim/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per period.
- summary.csv: mean RPS and pooled IR per phase (gross and net).
- search_log.csv: every half-life tried at every origin.
- forecasts.parquet: quintile probabilities and weights per period and asset.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation.calendar import cutoff, m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.covsim import CovarianceSimulation

HERE = Path(__file__).resolve().parent


def main(config_path: Path) -> None:
    config = load_config(config_path)
    data = config["data"]
    if not data["prices"]:
        sys.exit("config [data] prices is empty: the long-history snapshot comes from #12")
    prices = pd.read_parquet(m6.REPO_ROOT / data["prices"], columns=["symbol", "date", "price"])
    assets = sorted(m6.load_template()["ID"])
    end = cutoff(data["download_date"])["end"]
    calendar = resolve(m6_calendar(end), prices["date"].unique())

    ev = config["evaluation"]
    zero_variance = np.nan if ev["zero_variance"] == "nan" else float(ev["zero_variance"])
    spec = config["model"]
    out = prepare_run("covsim", config_path)
    periods, summaries, logs, forecasts = [], [], [], []
    for phase, policy in ev["policy"].items():
        model = CovarianceSimulation(
            halflives=tuple(spec["halflives"]),
            n_val=spec["n_val"],
            n_sims=spec["n_sims"],
            min_obs=spec["min_obs"],
            seed=spec["seed"],
        )
        subset = calendar[calendar["phase"] == phase]
        result = run(model, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
        tag = {"model": model.name, "phase": phase}
        periods.append(result.periods.assign(**tag))
        summaries.append({**result.summary(zero_variance), "phase": phase})
        logs.append(pd.DataFrame(model.search_log).assign(**tag))
        for label, f in result.forecasts.items():
            forecasts.append(f.probs.assign(weight=f.weights, label=label, **tag))
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(logs).to_csv(out / "search_log.csv", index=False)
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config.toml")
