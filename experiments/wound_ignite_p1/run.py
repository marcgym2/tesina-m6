"""Fidelity of wound-ignite's published code to the team's period-1 forecasts (#19).

    uv sync --project vendor/wound-ignite
    uv run python experiments/wound_ignite_p1/run.py

Writes results/wound_ignite_p1/<date>_<commit>/:
- team_months.csv: per submission, how far the team's forecast is from uniform, the
  gross exposure and the largest position (which months used the method at all).
- fidelity.csv: per checked period and seed, the reproduction against the submission:
  correlation of (p - 0.2), the least-squares shrinkage factor of the submission on the
  reproduction, the residual, and the RPS of submission, reproduction and uniform.
- seed_spread.csv: Monte Carlo spread of the reproduction across seeds.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tesina.data import m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset
from tesina.experiment import load_config, prepare_run
from tesina.models import RANK_COLUMNS
from tesina.models.external import PythonScriptModel

HERE = Path(__file__).resolve().parent
VENDOR = m6.REPO_ROOT / "vendor" / "wound-ignite"


def team_months(subs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for evaluation in m6.EVALUATIONS:
        g = subs[subs["Evaluation"] == evaluation]
        p = g[RANK_COLUMNS].to_numpy(dtype=float)
        w = g["Decision"].astype(float)
        top = g.loc[w.abs().idxmax()]
        rows.append(
            {
                "evaluation": evaluation,
                "mean_abs_dev_uniform": float(np.abs(p - 0.2).mean()),
                "max_abs_dev_uniform": float(np.abs(p - 0.2).max()),
                "gross_exposure": float(w.abs().sum()),
                "largest_position": top["Symbol"],
                "largest_weight": float(top["Decision"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    config = load_config(HERE / "config.toml")
    out = prepare_run("wound_ignite_p1", HERE / "config.toml")
    prices = m6.load_assets(config["data"]["snapshot"])
    subs = m6.load_submissions(config["data"]["snapshot"])
    subs = subs[subs["Team"] == config["team"]["id"]]
    team_months(subs).to_csv(out / "team_months.csv", index=False)

    calendar = resolve(m6_calendar(prices["date"].max()), prices["date"].unique())
    calendar = calendar.set_index("k")
    universe = sorted(prices["symbol"].unique())
    check = config["check"]
    fidelity, spread = [], []
    for k in check["periods"]:
        period = calendar.loc[k]
        origin = pd.Timestamp(period["base_date"])
        actual = subs[subs["Evaluation"] == period["label"]].set_index("Symbol")[RANK_COLUMNS]
        actual = actual.astype(float).loc[universe]
        targets = quintile_targets(
            period_returns(period_prices(prices, period["base_date"], period["end_date"]))
        )
        reproductions = []
        for seed in check["seeds"]:
            args = ["--seed", str(seed)] + (["--constant-dre"] if check["constant_dre"] else [])
            model = PythonScriptModel("wound_ignite", VENDOR, args=args, decisions=True)
            repro = model.forecast(prices[prices["date"] <= origin], universe, origin).probs
            reproductions.append(repro)
            x = (repro - 0.2).to_numpy().ravel()
            y = (actual - 0.2).to_numpy().ravel()
            shrink = float(x @ y / (x @ x))
            fidelity.append(
                {
                    "k": k,
                    "label": period["label"],
                    "origin": origin.date(),
                    "seed": seed,
                    "corr": float(np.corrcoef(x, y)[0, 1]) if y.std() > 0 else np.nan,
                    "shrink": shrink,
                    "mean_abs_resid": float(np.abs(y - shrink * x).mean()),
                    "max_abs_resid": float(np.abs(y - shrink * x).max()),
                    "rps_submission": float(rps_per_asset(actual, targets).mean()),
                    "rps_reproduction": float(rps_per_asset(repro, targets).mean()),
                    "rps_uniform": float(
                        rps_per_asset(pd.DataFrame(0.2, universe, RANK_COLUMNS), targets).mean()
                    ),
                }
            )
        stack = np.stack([r.to_numpy() for r in reproductions])
        spread.append(
            {
                "k": k,
                "max_abs_diff_across_seeds": float(np.ptp(stack, axis=0).max()),
                "mean_abs_diff_across_seeds": float(np.ptp(stack, axis=0).mean()),
            }
        )
    fidelity = pd.DataFrame(fidelity)
    fidelity.to_csv(out / "fidelity.csv", index=False)
    pd.DataFrame(spread).to_csv(out / "seed_spread.csv", index=False)
    print(fidelity.groupby("label").mean(numeric_only=True).round(4).to_string())
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
