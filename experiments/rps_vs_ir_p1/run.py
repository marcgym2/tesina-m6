"""RPS vs IR across the M6 teams in period 1 (issue #27, RQ3).

    uv run python experiments/rps_vs_ir_p1/run.py

Writes results/rps_vs_ir_p1/<date>_<commit>/:
- teams_global.csv: global RPS and IR per team, with forecast profile flags.
- correlations.csv: every pre-specified test (primary first).
- fisher_2x2.csv: beat-the-benchmark contingency table.
- fig_rps_ir_global.png, fig_spearman_monthly.png.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from tesina.analysis.correlation import correlation
from tesina.data import m6
from tesina.evaluation import leaderboard as lb
from tesina.experiment import load_config, prepare_run

HERE = Path(__file__).resolve().parent
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"


def forecast_profiles(subs: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """Per team over the 12 months: uniform forecasts, and exact benchmark copy."""
    s = subs[subs["Team"].isin(teams) & subs["Evaluation"].isin(lb.MONTHS)]
    uniform = s[m6.RANK_COLUMNS].sub(0.2).abs().max(axis=1) < 1e-9
    equal_w = (s["Decision"] - 0.01).abs() < 1e-9
    flags = pd.DataFrame({"Team": s["Team"], "uniform": uniform, "copy": uniform & equal_w})
    out = flags.groupby("Team").all()
    return out.rename(columns={"uniform": "uniform_forecast", "copy": "benchmark_copy"})


def figure_global(teams, bench, primary, path):
    fig, ax = plt.subplots(figsize=(6.3, 4.4), dpi=300)
    informative = teams[~teams["uniform_forecast"]]
    uniform = teams[teams["uniform_forecast"]]
    ax.axvline(0.16, color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.axhline(bench["ir"], color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.scatter(
        informative["rps"],
        informative["ir"],
        s=18,
        color=BLUE,
        edgecolor="white",
        linewidth=0.5,
        label="Equipos",
        zorder=2,
    )
    ax.scatter(
        uniform["rps"],
        uniform["ir"],
        s=24,
        marker="^",
        color=ORANGE,
        edgecolor="white",
        linewidth=0.5,
        label="Equipos con pronóstico uniforme",
        zorder=3,
    )
    ax.scatter(
        [bench["rps"]], [bench["ir"]], s=90, marker="*", color=INK, label="Benchmark M6", zorder=4
    )
    ax.set_xlabel("RPS global (menor es mejor)", color=INK)
    ax.set_ylabel("IR global (mayor es mejor)", color=INK)
    ax.set_title(
        f"Spearman ρ = {primary['estimate']:.2f} "
        f"[IC 95%: {primary['ci_low']:.2f}, {primary['ci_high']:.2f}], n = {primary['n']}",
        fontsize=9,
        color=INK,
    )
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def figure_monthly(monthly, path):
    fig, ax = plt.subplots(figsize=(6.3, 3.2), dpi=300)
    x = np.arange(1, len(monthly) + 1)
    ax.axhline(0, color=MUTED, lw=0.8, zorder=1)
    ax.errorbar(
        x,
        monthly["estimate"],
        yerr=[monthly["estimate"] - monthly["ci_low"], monthly["ci_high"] - monthly["estimate"]],
        fmt="o",
        color=BLUE,
        ecolor=BLUE,
        elinewidth=1.2,
        capsize=0,
        markersize=5,
        zorder=2,
    )
    ax.set_xticks(x)
    ax.set_xlabel("Mes de la competencia", color=INK)
    ax.set_ylabel("Spearman ρ (RPS, IR)", color=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    config = load_config(HERE / "config.toml")
    out = prepare_run("rps_vs_ir_p1", HERE / "config.toml")
    snap = config["data"]["snapshot"]
    zv = float(config["evaluation"]["zero_variance"])
    a = config["analysis"]
    kw = {"n_boot": a["n_boot"], "n_perm": a["n_perm"], "level": a["level"], "seed": a["seed"]}

    subs = m6.load_submissions(snap)
    scores = lb.score_submissions(subs, m6.load_assets(snap), m6.load_period1_calendar(snap))
    teams = lb.summarize(scores, lb.MONTHS, zero_variance=zv).set_index("team")
    teams = teams.join(forecast_profiles(subs, list(teams.index)))
    teams.to_csv(out / "teams_global.csv")
    bench = teams.loc[config["evaluation"]["benchmark_team"]]

    rows = []

    def add(name, population, x, y, method):
        rows.append({"analysis": name, "population": population, **correlation(x, y, method, **kw)})

    add("spearman_global_all", "163 global teams", teams["rps"], teams["ir"], "spearman")
    add("pearson_global_all", "163 global teams", teams["rps"], teams["ir"], "pearson")
    inf = teams[~teams["uniform_forecast"]]
    add(
        "spearman_global_informative",
        "global teams without uniform forecasts",
        inf["rps"],
        inf["ir"],
        "spearman",
    )
    monthly = []
    for i, month in enumerate(lb.MONTHS, start=1):
        t = lb.summarize(scores, [month], zero_variance=zv)
        add(f"spearman_month_{i:02d}", f"teams scored in {month}", t["rps"], t["ir"], "spearman")
        monthly.append(rows[-1])

    better_rps = teams["rps"].round(lb.RPS_RANK_DECIMALS) < 0.16
    better_ir = teams["ir"] > bench["ir"]
    table = pd.crosstab(better_rps.rename("beats_rps"), better_ir.rename("beats_ir"))
    table.to_csv(out / "fisher_2x2.csv")
    fisher = stats.fisher_exact(table.to_numpy())
    rows.append(
        {
            "analysis": "fisher_beat_benchmark",
            "population": "163 global teams",
            "method": "fisher_exact",
            "n": int(table.to_numpy().sum()),
            "estimate": float(fisher.statistic),
            "p_perm": float(fisher.pvalue),
        }
    )

    results = pd.DataFrame(rows)
    results.to_csv(out / "correlations.csv", index=False)
    figure_global(teams, bench, rows[0], out / "fig_rps_ir_global.png")
    figure_monthly(pd.DataFrame(monthly), out / "fig_spearman_monthly.png")
    print(
        results[["analysis", "n", "estimate", "ci_low", "ci_high", "p_perm"]].round(3).to_string()
    )
    print(f"{len(results)} tests reported; results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
