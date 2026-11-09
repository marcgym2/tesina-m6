"""Every model against the uniform benchmark in both periods (issues #26, #27, #28).

    uv run python experiments/model_comparison/run.py

Reads the most recent run of each experiment in results/ and writes
results/model_comparison/<date>_<commit>/:
- inputs.json: the run directory used for each experiment.
- scores.csv: per model-weighting and phase, mean RPS, mean RPS of the benchmark on the
  same periods, pooled IR gross and net.
- significance.csv: paired tests of RPS against uniform per family (DM-HLN, block
  bootstrap, Holm and Benjamini-Hochberg).
- persistence.csv: RQ1, period 1 against period 2 for the M6 teams' methods.
- rps_vs_ir.csv: RQ3 at model level in period 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tesina.analysis.correlation import correlation
from tesina.analysis.significance import adjust_pvalues, block_bootstrap, diebold_mariano
from tesina.experiment import REPO_ROOT, RESULTS, load_config, prepare_run

HERE = Path(__file__).resolve().parent


def latest(experiment: str) -> Path:
    runs = sorted(p for p in (RESULTS / experiment).iterdir() if p.is_dir())
    clean = [p for p in runs if not p.name.endswith("-dirty")]
    if not clean:
        raise FileNotFoundError(f"no clean run of {experiment} in results/")
    return clean[-1]


def load_periods(experiment: str) -> pd.DataFrame:
    df = pd.read_csv(latest(experiment) / "periods.csv", parse_dates=["origin", "end_date"])
    if "evaluation" in df.columns:  # baselines: keep the two main evaluations
        df = df[df["evaluation"].isin(["period1", "period2"])]
        df = df.rename(columns={"evaluation": "phase"})
    return df


def test_family(diffs: dict[str, pd.Series], cfg: dict, block: int) -> pd.DataFrame:
    t, b = cfg["test"], cfg["bootstrap"]
    rows = []
    for name, d in diffs.items():
        dm = diebold_mariano(d.to_numpy(), h=t["horizon"], alternative=t["alternative"])
        bb = block_bootstrap(d.to_numpy(), block, b["n_boot"], b["seed"], t["alternative"])
        rows.append(
            {
                "model": name,
                "n_periods": dm["n"],
                "mean_rps_diff": dm["mean_diff"],
                "share_periods_better": float((d < 0).mean()),
                "dm_stat": dm["dm_stat"],
                "p_dm": dm["p_value"],
                "p_boot": bb["p_boot"],
                "boot_ci_low": bb["ci_low"],
                "boot_ci_high": bb["ci_high"],
            }
        )
    table = pd.DataFrame(rows)
    table["p_holm"] = adjust_pvalues(table["p_dm"], "holm")
    table["p_bh"] = adjust_pvalues(table["p_dm"], "bh")
    return table.sort_values("p_dm").reset_index(drop=True)


def verdict(row: pd.Series, alpha: float) -> str:
    if row["p_holm"] < alpha:
        return "persiste"
    if row["boot_ci_low"] > 0:
        return "peor que el uniforme"
    return "no se distingue del uniforme"


def main() -> None:
    cfg = load_config(HERE / "config.toml")
    out = prepare_run("model_comparison", HERE / "config.toml")
    experiments = sorted({cfg["inputs"]["benchmark"], *cfg["inputs"]["models"]})
    inputs = {e: str(latest(e).relative_to(REPO_ROOT)) for e in experiments}
    (out / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")

    frames = {e: load_periods(e) for e in experiments}
    bench = frames[cfg["inputs"]["benchmark"]]
    bench = bench[bench["model"] == "uniform"].set_index(["phase", "k"])
    everything = pd.concat(frames.values(), ignore_index=True)
    everything = everything.join(
        bench[["rps", "ir_net"]].rename(columns={"rps": "rps_uniform", "ir_net": "ir_net_bench"}),
        on=["phase", "k"],
    )
    everything["rps_diff"] = everything["rps"] - everything["rps_uniform"]
    everything.to_csv(out / "periods_all.csv", index=False)

    # Scores per model-weighting and phase. The pooled IR comes from each run's summary.
    summaries = []
    for e in experiments:
        s = pd.read_csv(latest(e) / "summary.csv")
        if "evaluation" in s.columns:
            s = s[s["evaluation"].isin(["period1", "period2"])]
            s = s.rename(columns={"evaluation": "phase"})
        summaries.append(s[["model", "phase", "n_periods", "rps", "ir", "ir_net"]])
    scores = pd.concat(summaries, ignore_index=True)
    mean_bench = everything.groupby(["model", "phase"])["rps_uniform"].mean()
    scores = scores.join(mean_bench, on=["model", "phase"])
    scores["rps_diff"] = scores["rps"] - scores["rps_uniform"]
    scores.to_csv(out / "scores.csv", index=False)

    # Significance: one tested model per experiment.
    tested = cfg["inputs"]["models"]
    after = pd.Timestamp(cfg["subperiods"]["after_pretraining"])
    families = {
        "period2": (everything["phase"] == "period2", cfg["bootstrap"]["block"]["period2"]),
        "period1": (everything["phase"] == "period1", cfg["bootstrap"]["block"]["period1"]),
        "period2_after_pretraining": (
            (everything["phase"] == "period2") & (everything["origin"] > after),
            cfg["bootstrap"]["block"]["period2"],
        ),
    }
    tables = []
    for family, (mask, block) in families.items():
        sub = everything[mask]
        diffs = {
            experiment: sub[sub["model"] == model].sort_values("k")["rps_diff"]
            for experiment, model in tested.items()
        }
        tables.append(test_family(diffs, cfg, block).assign(family=family))
    significance = pd.concat(tables, ignore_index=True)
    significance.to_csv(out / "significance.csv", index=False)

    # RQ1: persistence of the M6 teams' methods.
    alpha = cfg["test"]["alpha"]
    p1 = significance[significance["family"] == "period1"].set_index("model")
    p2 = significance[significance["family"] == "period2"].set_index("model")
    rows = []
    for method in cfg["persistence"]["methods"]:
        rows.append(
            {
                "method": method,
                "rps_diff_period1": p1.loc[method, "mean_rps_diff"],
                "p_dm_period1": p1.loc[method, "p_dm"],
                "rps_diff_period2": p2.loc[method, "mean_rps_diff"],
                "p_dm_period2": p2.loc[method, "p_dm"],
                "p_holm_period2": p2.loc[method, "p_holm"],
                "ci_low_period2": p2.loc[method, "boot_ci_low"],
                "ci_high_period2": p2.loc[method, "boot_ci_high"],
                "verdict": verdict(p2.loc[method], alpha),
            }
        )
    pd.DataFrame(rows).to_csv(out / "persistence.csv", index=False)

    # RQ3 at model level, period 2.
    s2 = scores[scores["phase"] == "period2"].dropna(subset=["rps", "ir_net"])
    r = cfg["rps_vs_ir"]
    rows = [
        {
            "x": "rps",
            "y": y,
            **correlation(s2["rps"], s2[y], "spearman", r["n_boot"], r["n_perm"], seed=r["seed"]),
        }
        for y in ("ir_net", "ir")
    ]
    pd.DataFrame(rows).to_csv(out / "rps_vs_ir.csv", index=False)

    with pd.option_context("display.width", 200):
        print(scores.round(5).to_string(index=False))
        cols = [
            "family",
            "model",
            "n_periods",
            "mean_rps_diff",
            "share_periods_better",
            "p_dm",
            "p_holm",
            "p_boot",
        ]
        print(significance[cols].round(5).to_string(index=False))
    print(f"results in {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
