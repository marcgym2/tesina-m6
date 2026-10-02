"""AdaGaussMC (reimplementation) on periods 1 and 2, with a period-1 fidelity check (#20).

    uv run python experiments/adagaussmc/run.py [config.toml]

Writes results/adagaussmc/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per period.
- summary.csv: mean RPS and pooled IR per phase (gross and net).
- fidelity.csv: period 1, reproduction against the team's submission per period:
  correlation of (p - 0.2), mean absolute difference, and RPS of both.
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
from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.experiment import load_config, prepare_run
from tesina.models import RANK_COLUMNS
from tesina.models.adagaussmc import AdaGaussMC

HERE = Path(__file__).resolve().parent


def fidelity(result, prices, subs) -> pd.DataFrame:
    rows = []
    for period in result.periods.itertuples():
        repro = result.forecasts[period.label].probs
        actual = subs[subs["Evaluation"] == period.label].set_index("Symbol")[RANK_COLUMNS]
        actual = actual.astype(float).loc[repro.index]
        targets = quintile_targets(
            period_returns(period_prices(prices, period.origin, period.end_date)[repro.index])
        )
        x, y = (repro - 0.2).to_numpy().ravel(), (actual - 0.2).to_numpy().ravel()
        rows.append(
            {
                "k": period.k,
                "label": period.label,
                "corr": float(np.corrcoef(x, y)[0, 1]) if y.std() > 0 else np.nan,
                "mean_abs_diff": float(np.abs(x - y).mean()),
                "max_abs_diff": float(np.abs(x - y).max()),
                "rps_submission": float(rps_per_asset(actual, targets).mean()),
                "rps_reproduction": float(rps_per_asset(repro, targets).mean()),
            }
        )
    return pd.DataFrame(rows)


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
    model = AdaGaussMC(
        class_window=tuple(spec["class_window"]),
        vol_start=spec["vol_start"],
        horizon=spec["horizon"],
        min_obs=spec["min_obs"],
        theta0=tuple(spec["theta0"]),
        eta=spec["eta"],
        n_sims=spec["n_sims"],
        seed=spec["seed"],
    )
    out = prepare_run("adagaussmc", config_path)
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
            fidelity(result, prices, subs).to_csv(out / "fidelity.csv", index=False)
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config.toml")
