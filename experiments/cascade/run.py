"""Bias cascade on the GBM, period 2 (RQ4, issues #24 and #25).

    uv run python experiments/cascade/run.py

Writes results/cascade/<date>_<commit>/:
- cascade.csv: per step, mean RPS, RPS of the uniform benchmark on the same universe,
  their difference with a paired test, pooled IR, annualised Sharpe and turnover.
- periods.csv: the same per period and step.
- search.csv: every configuration tried in the steps that select ex post.
- cascade.png: the figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tesina import cascade as cs
from tesina.analysis.significance import block_bootstrap, diebold_mariano
from tesina.backtest.walk_forward import run
from tesina.data import eodhd, m6
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.evaluation.ir import information_ratio
from tesina.experiment import RESULTS, load_config, prepare_run
from tesina.models.baselines import Uniform
from tesina.models.gbm import GBM
from tesina.models.weighting import Reweighted

HERE = Path(__file__).resolve().parent
STEPS = {
    "s0": "Ingenuo",
    "s1": "+ split temporal",
    "s2": "+ purga de etiquetas",
    "s3": "+ preprocesamiento solo con el pasado",
    "s4": "+ selección honesta",
    "s5": "+ universo point-in-time",
    "s6": "+ costos de transacción",
}


def main() -> None:
    cfg = load_config(HERE / "config.toml")
    data, ev, nv, t = cfg["data"], cfg["evaluation"], cfg["naive"], cfg["test"]
    out = prepare_run("cascade", HERE / "config.toml")

    core = eodhd.load_prices(data["eodhd"])
    extra = eodhd.load_prices(data["eodhd"], "eodhd_successors")
    prices = pd.concat([core, extra], ignore_index=True)
    end = eodhd.snapshot(data["eodhd"])["cutoff_end"]
    calendar = resolve(m6_calendar(end), core["date"].unique())
    periods = calendar[calendar["phase"] == ev["phase"]]
    origins = [pd.Timestamp(d) for d in periods["base_date"]]
    assets = sorted(m6.load_template()["ID"])
    survivors = cs.survivors_universe(assets)
    survivor_prices = prices[prices["symbol"].isin(survivors)]

    def evaluate(probs: dict, universe_prices, policy, members):
        model = Reweighted(probs, "expected_rank", name="step")
        return run(model, universe_prices, periods, policy, ev["cost_bps"], np.nan, members)

    def mean_rps(probs: dict) -> float:
        return float(evaluate(probs, survivor_prices, "official", survivors).periods["rps"].mean())

    wide = cs.to_wide(prices, survivors)
    naive = cs.naive_features(wide)
    clean = cs.cross_sectional_features(wide)
    weekly = cs.weekly_dataset(wide, naive, origins, nv["step_days"])
    seed, threads = nv["seed"], nv["threads"]

    candidates = {
        "s0": cs.kfold_forecasts(weekly, origins, k=nv["folds"], seed=seed, threads=threads)
    }
    print("s0 done", flush=True)
    candidates["s1"] = cs.walk_forward_forecasts(
        lambda o: weekly[weekly["base"] < o],
        lambda o: weekly[weekly["base"] == o],
        origins,
        seed=seed,
        threads=threads,
    )
    print("s1 done", flush=True)
    for step, features in (("s2", naive), ("s3", clean)):
        cache: dict = {}
        candidates[step] = cs.walk_forward_forecasts(
            lambda o, f=features, c=cache: cs.window_dataset(wide, f, o, c),
            lambda o, f=features: cs.origin_rows(f, o, survivors),
            origins,
            seed=seed,
            threads=threads,
        )
        print(step, "done", flush=True)

    chosen, searches = {}, []
    for step, cands in candidates.items():
        best, table = cs.select_ex_post(cands, mean_rps)
        chosen[step] = cands[best]
        searches.append(
            table.assign(
                step=step, chosen=lambda d, b=best: (d["config"] == b[0]) & (d["rounds"] == b[1])
            )
        )
    pd.concat(searches).to_csv(out / "search.csv", index=False)

    gbm = GBM()
    chosen["s4"] = {
        o: gbm.forecast(survivor_prices[survivor_prices["date"] <= o], survivors, o).probs
        for o in origins
    }
    print("s4 done", flush=True)
    f = pd.read_parquet(RESULTS / "gbm" / cfg["clean"]["gbm_run"] / "forecasts.parquet")
    f = f[(f["phase"] == ev["phase"]) & (f["model"] == "gbm_equal")]
    by_label = {label: g.set_index("symbol")[cs.RANK_COLUMNS] for label, g in f.groupby("label")}
    pit = {o: by_label[label] for o, label in zip(origins, periods["label"], strict=True)}

    rows, per_period = [], []
    for step, name in STEPS.items():
        if step in ("s5", "s6"):
            result = evaluate(pit, core, "d2", assets)
            bench = run(Uniform(), core, periods, "d2", ev["cost_bps"], np.nan, assets)
        else:
            result = evaluate(chosen[step], survivor_prices, "official", survivors)
            bench = run(
                Uniform(), survivor_prices, periods, "official", ev["cost_bps"], np.nan, survivors
            )
        net = step == "s6"
        logs = result.log_returns_net if net else result.log_returns
        pooled = pd.concat([logs[k] for k in result.periods["label"]])
        d = (result.periods["rps"] - bench.periods["rps"]).to_numpy()
        dm = diebold_mariano(d, h=t["horizon"], alternative=t["alternative"])
        bb = block_bootstrap(d, t["block"], t["n_boot"], t["seed"], t["alternative"])
        bench_logs = pd.concat(
            [
                bench.log_returns_net[k] if net else bench.log_returns[k]
                for k in bench.periods["label"]
            ]
        )
        rows.append(
            {
                "step": step,
                "name": name,
                "rps": float(result.periods["rps"].mean()),
                "rps_uniform": float(bench.periods["rps"].mean()),
                "rps_diff": dm["mean_diff"],
                "p_dm": dm["p_value"],
                "ci_low": bb["ci_low"],
                "ci_high": bb["ci_high"],
                "ir": information_ratio(pooled),
                "ir_benchmark": information_ratio(bench_logs),
                "sharpe": cs.annualized_sharpe(pooled),
                "sharpe_benchmark": cs.annualized_sharpe(bench_logs),
                "turnover": float(result.periods["turnover"].mean()),
                "net_of_costs": net,
            }
        )
        per_period.append(result.periods.assign(step=step, rps_uniform=bench.periods["rps"]))
    table = pd.DataFrame(rows)
    table.to_csv(out / "cascade.csv", index=False)
    pd.concat(per_period).to_csv(out / "periods.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    y = np.arange(len(table))[::-1]
    axes[0].barh(y, -table["rps_diff"], color="#4C6A92", height=0.6)
    axes[0].set_yticks(y, list(STEPS.values()), fontsize=8)
    axes[0].set_xlabel("Mejora de RPS sobre el uniforme")
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[1].barh(y, table["sharpe"], color="#4C6A92", height=0.6)
    axes[1].axvline(
        table["sharpe_benchmark"].iloc[-1], color="#B5523B", linewidth=1.2, linestyle="--"
    )
    axes[1].set_yticks(y, [])
    axes[1].set_xlabel("Sharpe anualizado (línea: pesos iguales)")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "cascade.png", dpi=200)

    print(table.round(5).to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
