"""Significance of RPS improvements over the uniform benchmark, period 1 (issue #26).

    uv run python experiments/significance_p1/run.py

Writes results/significance_p1/<date>_<commit>/:
- models.csv: our models vs Uniform.
- teams.csv: the 163 teams of the global leaderboard vs Uniform.
- summary.csv: per family, number of comparisons and of significant ones (raw,
  Holm, Benjamini-Hochberg).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tesina.analysis.significance import adjust_pvalues, block_bootstrap, diebold_mariano
from tesina.backtest.walk_forward import run
from tesina.data import m6
from tesina.evaluation import leaderboard as lb
from tesina.evaluation.calendar import m6_calendar, resolve
from tesina.experiment import load_config, prepare_run
from tesina.models.baselines import HistoricalFrequency, Uniform

HERE = Path(__file__).resolve().parent
MODELS = {"historical_frequency": HistoricalFrequency}


def test_family(diffs: dict[str, pd.Series], cfg: dict) -> pd.DataFrame:
    t, b = cfg["test"], cfg["bootstrap"]
    rows = []
    for name, d in diffs.items():
        dm = diebold_mariano(d.to_numpy(), h=t["horizon"], alternative=t["alternative"])
        bb = block_bootstrap(
            d.to_numpy(), b["block"], b["n_boot"], b["seed"], alternative=t["alternative"]
        )
        rows.append(
            {
                "name": name,
                "n_periods": dm["n"],
                "mean_rps_diff": dm["mean_diff"],
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


def summarize(name: str, table: pd.DataFrame, alpha: float) -> dict:
    return {
        "family": name,
        "comparisons": len(table),
        "mean_diff_below_zero": int((table["mean_rps_diff"] < 0).sum()),
        "significant_raw": int((table["p_dm"] < alpha).sum()),
        "significant_holm": int((table["p_holm"] < alpha).sum()),
        "significant_bh": int((table["p_bh"] < alpha).sum()),
        "significant_boot_raw": int((table["p_boot"] < alpha).sum()),
    }


def main() -> None:
    cfg = load_config(HERE / "config.toml")
    out = prepare_run("significance_p1", HERE / "config.toml")
    snap = cfg["data"]["snapshot"]
    prices = m6.load_assets(snap)
    calendar = resolve(m6_calendar(prices["date"].max()), prices["date"].unique())
    period1 = calendar[calendar["phase"] == "period1"]

    uniform = run(Uniform(), prices, period1).periods.set_index("label")["rps"]

    model_diffs = {}
    for name in cfg["families"]["models"]:
        rps = run(MODELS[name](), prices, period1).periods.set_index("label")["rps"]
        model_diffs[name] = rps - uniform
    models = test_family(model_diffs, cfg)
    models.to_csv(out / "models.csv", index=False)

    scores = lb.score_submissions(m6.load_submissions(snap), prices, m6.load_period1_calendar(snap))
    team_diffs = {
        team: pd.Series([scores.rps[team, e] for e in lb.MONTHS], index=lb.MONTHS)
        - uniform.loc[lb.MONTHS].to_numpy()
        for team in scores.teams(lb.MONTHS[0])
    }
    teams = test_family(team_diffs, cfg)
    names = m6.load_leaderboard("global", snap).set_index("team")["team_name"]
    teams.insert(1, "team_name", teams["name"].map(names))
    teams.to_csv(out / "teams.csv", index=False)

    alpha = cfg["test"]["alpha"]
    summary = pd.DataFrame([summarize("models", models, alpha), summarize("teams", teams, alpha)])
    summary.to_csv(out / "summary.csv", index=False)
    print(models.round(4).to_string(index=False))
    print(teams.head(10).round(4).to_string(index=False))
    print(summary.to_string(index=False))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
