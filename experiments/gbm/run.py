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
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation.calendar import cutoff, m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models import Forecast
from tesina.models.baselines import equal_weights
from tesina.models.gbm import GBM, expected_rank_weights

HERE = Path(__file__).resolve().parent


@dataclass
class Reweighted:
    """Replays fitted probabilities (by origin) with a given weighting rule."""

    probs: dict[pd.Timestamp, pd.DataFrame]
    weighting: str
    name: str

    def forecast(self, history, universe, origin) -> Forecast:
        probs = self.probs[pd.Timestamp(origin)]
        if self.weighting == "equal":
            return Forecast(probs, equal_weights(universe))
        if self.weighting == "expected_rank":
            return Forecast(probs, expected_rank_weights(probs))
        raise ValueError(f"unknown weighting {self.weighting!r}")


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
    out = prepare_run("gbm", config_path)
    periods, summaries, logs, forecasts = [], [], [], []
    for phase, policy in ev["policy"].items():
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
