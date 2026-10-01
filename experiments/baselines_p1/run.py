"""Baselines on period 1 (issue #16).

    uv run python experiments/baselines_p1/run.py

Writes results/baselines_p1/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per model and period.
- summary.csv: mean RPS and pooled IR per model (gross and net).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.baselines import HistoricalFrequency, Uniform

HERE = Path(__file__).resolve().parent


def main() -> None:
    config = load_config(HERE / "config.toml")
    out = prepare_run("baselines_p1", HERE / "config.toml")
    prices = m6.load_assets(config["data"]["snapshot"])
    calendar = resolve(m6_calendar(prices["date"].max()), prices["date"].unique())
    period1 = calendar[calendar["phase"] == "period1"]

    hf = config["models"]["historical_frequency"]
    lookback = None if hf["lookback"] == "expanding" else int(hf["lookback"])
    models = [Uniform(), HistoricalFrequency(lookback=lookback, alpha=hf["alpha"])]

    ev = config["evaluation"]
    periods, summaries = [], []
    for model in models:
        result = run(model, prices, period1, ev["universe_policy"], ev["cost_bps"])
        periods.append(result.periods.assign(model=model.name))
        summaries.append(result.summary())
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
