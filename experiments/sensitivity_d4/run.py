"""Sensitivity D4: every model on period 2 with the official M6 universe rule.

    uv run python experiments/sensitivity_d4/run.py

Writes results/sensitivity_d4/<date>_<commit>/:
- periods.csv: RPS and universe size per model and period.
- summary.csv: per model, mean RPS difference against uniform with the paired test,
  next to nothing else: the main analysis (policy D2) is in results/model_comparison.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tesina.analysis.significance import adjust_pvalues, block_bootstrap, diebold_mariano
from tesina.backtest.walk_forward import run
from tesina.data import eodhd, m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import REPO_ROOT, load_config, prepare_run
from tesina.models.adagaussmc import AdaGaussMC
from tesina.models.baselines import HistoricalFrequency, Uniform
from tesina.models.covsim import CovarianceSimulation
from tesina.models.external import PythonScriptModel, RScriptModel
from tesina.models.foundation import TimesFM
from tesina.models.gbm import GBM

HERE = Path(__file__).resolve().parent


def models() -> dict:
    """Each model with the settings of its own experiment (their defaults)."""
    vendor = REPO_ROOT / "vendor"
    return {
        "baselines": HistoricalFrequency(),
        "covsim": CovarianceSimulation(),
        "adagaussmc": AdaGaussMC(),
        "gbm": GBM(),
        "timesfm": TimesFM(),
        "finqboost": RScriptModel(
            "finqboost", vendor / "finqboost", substitutes={"VXX": "VIXY"}, start="2007-01-01"
        ),
        "wound_ignite": PythonScriptModel(
            "wound_ignite", vendor / "wound-ignite", args=["--seed", "0"], decisions=True
        ),
    }


def main() -> None:
    cfg = load_config(HERE / "config.toml")
    data, ev, t = cfg["data"], cfg["evaluation"], cfg["test"]
    out = prepare_run("sensitivity_d4", HERE / "config.toml")
    prices = eodhd.phase_prices(data["eodhd"], data["m6_snapshot"])[ev["phase"]]
    assets = sorted(m6.load_template()["ID"])
    end = eodhd.snapshot(data["eodhd"])["cutoff_end"]
    calendar = resolve(m6_calendar(end), prices["date"].unique())
    periods = calendar[calendar["phase"] == ev["phase"]]

    def evaluate(model):
        return run(model, prices, periods, ev["policy"], ev["cost_bps"], np.nan, assets).periods

    bench = evaluate(Uniform())
    frames, rows = [bench.assign(model="uniform")], []
    for name, model in models().items():
        p = evaluate(model)
        frames.append(p.assign(model=name))
        d = (p["rps"] - bench["rps"]).to_numpy()
        dm = diebold_mariano(d, h=t["horizon"], alternative=t["alternative"])
        bb = block_bootstrap(d, t["block"], t["n_boot"], t["seed"], t["alternative"])
        rows.append(
            {
                "model": name,
                "n_periods": dm["n"],
                "mean_rps_diff": dm["mean_diff"],
                "share_periods_better": float((d < 0).mean()),
                "p_dm": dm["p_value"],
                "boot_ci_low": bb["ci_low"],
                "boot_ci_high": bb["ci_high"],
            }
        )
        print(name, round(dm["mean_diff"], 5), flush=True)
    pd.concat(frames).to_csv(out / "periods.csv", index=False)
    summary = pd.DataFrame(rows)
    summary["p_holm"] = adjust_pvalues(summary["p_dm"], "holm")
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.round(5).to_string(index=False))
    print(f"results in {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
