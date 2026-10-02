"""Multiclass GBM on periods 1 and 2 (issue #21).

    uv run python experiments/gbm/run.py [config.toml]

Writes results/gbm/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per weighting and period.
- summary.csv: mean RPS and pooled IR per weighting and phase (gross and net).
- search_log.csv: every hyper-parameter configuration tried at every origin.
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
from tesina.models.gbm import GBM
from tesina.models.weighting import Reweighted

HERE = Path(__file__).resolve().parent


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
    out = prepare_run("gbm", config_path)
    periods, summaries, logs, forecasts = [], [], [], []
    for phase, policy in ev["policy"].items():
        prices = prices_by_phase[phase]
        calendar = resolve(m6_calendar(end), prices["date"].unique())
        subset = calendar[calendar["phase"] == phase]
        gbm = GBM(
            grid=spec["grid"],
            n_val=spec["n_val"],
            embargo=spec["embargo"],
            min_train_windows=spec["min_train_windows"],
            lookback=None if spec["lookback"] == "expanding" else int(spec["lookback"]),
            max_rounds=spec["max_rounds"],
            early_stopping=spec["early_stopping"],
            seed=spec["seed"],
        )
        fitted = run(gbm, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
        logs.append(pd.DataFrame(gbm.search_log).assign(phase=phase))
        probs = {
            origin: fitted.forecasts[label].probs
            for origin, label in zip(fitted.periods["origin"], fitted.periods["label"], strict=True)
        }
        for weighting in spec["weightings"]:
            # The quintile probabilities are fitted once per phase; weightings only map
            # them to positions, so the search is not repeated (or double-counted).
            model = Reweighted(probs, weighting, name=f"gbm_{weighting}")
            result = run(model, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
            tag = {"model": model.name, "phase": phase}
            periods.append(result.periods.assign(**tag))
            summaries.append({**result.summary(zero_variance), "phase": phase})
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
