"""Baselines on periods 1 and 2 (issues #15, #16), including the D4 sensitivity.

    uv run python experiments/baselines/run.py

Writes results/baselines/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net), turnover and universe size per model and period.
- summary.csv: mean RPS and pooled IR per model and evaluation (gross and net).
- forecasts.parquet: quintile probabilities and weights per period and asset.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import eodhd, m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.baselines import HistoricalFrequency, Uniform

HERE = Path(__file__).resolve().parent


def main() -> None:
    config = load_config(HERE / "config.toml")
    data, ev = config["data"], config["evaluation"]
    prices_by_phase = eodhd.phase_prices(data["eodhd"], data["m6_snapshot"])
    assets = sorted(m6.load_template()["ID"])
    end = eodhd.snapshot(data["eodhd"])["cutoff_end"]
    zero_variance = np.nan if ev["zero_variance"] == "nan" else float(ev["zero_variance"])
    hf = config["models"]["historical_frequency"]
    lookback = None if hf["lookback"] == "expanding" else int(hf["lookback"])
    out = prepare_run("baselines", HERE / "config.toml")

    periods, summaries, forecasts = [], [], []
    for evaluation, policy in ev["policy"].items():
        phase = evaluation.split("_")[0]
        prices = prices_by_phase[phase]
        calendar = resolve(m6_calendar(end), prices["date"].unique())
        subset = calendar[calendar["phase"] == phase]
        for model in (Uniform(), HistoricalFrequency(lookback=lookback, alpha=hf["alpha"])):
            result = run(model, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
            tag = {"model": model.name, "evaluation": evaluation}
            periods.append(result.periods.assign(**tag))
            summaries.append({**result.summary(zero_variance), "evaluation": evaluation})
            for label, f in result.forecasts.items():
                forecasts.append(f.probs.assign(weight=f.weights, label=label, **tag))
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
