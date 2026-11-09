"""FinQBoost on periods 1 and 2, with a period-1 fidelity check (issue #17).

    uv run python experiments/finqboost/run.py

Needs R with the renv library of vendor/finqboost. Writes results/finqboost/<date>_<commit>/:
- periods.csv, summary.csv: RPS, IR (gross and net) and turnover per period and phase.
- fidelity.csv: period 1, the re-run against the team's actual submission per period.
- forecasts.parquet: quintile probabilities and weights per period and asset.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tesina.analysis.fidelity import compare_with_submissions
from tesina.backtest.walk_forward import run
from tesina.data import eodhd, m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.external import RScriptModel

HERE = Path(__file__).resolve().parent


def main() -> None:
    config = load_config(HERE / "config.toml")
    data, ev, spec = config["data"], config["evaluation"], config["model"]
    prices_by_phase = eodhd.phase_prices(data["eodhd"], data["m6_snapshot"])
    assets = sorted(m6.load_template()["ID"])
    end = eodhd.snapshot(data["eodhd"])["cutoff_end"]
    zero_variance = np.nan if ev["zero_variance"] == "nan" else float(ev["zero_variance"])
    model = RScriptModel(
        "finqboost",
        m6.REPO_ROOT / "vendor" / "finqboost",
        substitutes=dict(spec["substitutes"]),
        start=spec["start"],
    )
    out = prepare_run("finqboost", HERE / "config.toml")
    subs = m6.load_submissions(data["m6_snapshot"])
    subs = subs[subs["Team"] == config["team"]["id"]]
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
        if phase == "period1":
            compare_with_submissions(result, prices, subs).to_csv(out / "fidelity.csv", index=False)
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
