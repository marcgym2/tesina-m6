"""Zero-shot TimesFM-3 on periods 1 and 2 (issue #23).

    uv sync --extra timesfm
    uv run python experiments/timesfm/run.py [config.toml]

Needs the TimesFM-3 weights (non-commercial licence, docs/timesfm.md); they are
downloaded to the Hugging Face cache on first use, never into the repository.

Writes results/timesfm/<date>_<commit>/:
- periods.csv: RPS, IR (gross and net) and turnover per weighting and period.
- summary.csv: mean RPS and pooled IR per weighting and phase (gross and net).
- deciles.parquet: forecast deciles of each asset's log return per origin.
- forecasts.parquet: quintile probabilities and weights per period and asset.
- model_info.json: checkpoint, revision and package version.
"""

from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation.calendar import cutoff, m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.foundation import CHECKPOINT, REVISION, TimesFM, TimesFM3Backend
from tesina.models.weighting import Reweighted

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
    out = prepare_run("timesfm", config_path)
    info = {"checkpoint": CHECKPOINT, "revision": REVISION, "timesfm": metadata.version("timesfm")}
    (out / "model_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    backend = TimesFM3Backend()
    periods, summaries, deciles, forecasts = [], [], [], []
    for phase, policy in ev["policy"].items():
        subset = calendar[calendar["phase"] == phase]
        model = TimesFM(
            backend=backend,
            context=spec["context"],
            horizon=spec["horizon"],
            min_context=spec["min_context"],
            copula_halflife=spec["copula_halflife"],
            n_sims=spec["n_sims"],
            seed=spec["seed"],
        )
        fitted = run(model, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
        for origin, d in model.deciles_log.items():
            named = d.rename(columns=lambda q: f"q{q:.1f}")
            deciles.append(named.assign(origin=origin, phase=phase))
        probs = {
            origin: fitted.forecasts[label].probs
            for origin, label in zip(fitted.periods["origin"], fitted.periods["label"], strict=True)
        }
        for weighting in spec["weightings"]:
            replay = Reweighted(probs, weighting, name=f"timesfm3_{weighting}")
            result = run(replay, prices, subset, policy, ev["cost_bps"], zero_variance, assets)
            tag = {"model": replay.name, "phase": phase}
            periods.append(result.periods.assign(**tag))
            summaries.append({**result.summary(zero_variance), "phase": phase})
            for label, f in result.forecasts.items():
                forecasts.append(f.probs.assign(weight=f.weights, label=label, **tag))
    pd.concat(periods).to_csv(out / "periods.csv", index=False)
    pd.concat(deciles).rename_axis("symbol").reset_index().to_parquet(out / "deciles.parquet")
    pd.concat(forecasts).rename_axis("symbol").reset_index().to_parquet(out / "forecasts.parquet")
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config.toml")
