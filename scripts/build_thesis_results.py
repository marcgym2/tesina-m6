"""Generate the numbers and tables of chapter 7 from results/ (CLAUDE.md: no result is
typed by hand in the thesis).

    uv run python scripts/build_thesis_results.py

Writes:
- ``thesis/_variables.yml``: every figure quoted in the text, used as ``{{< var key >}}``.
- ``thesis/_generated/tbl-*.md``: Markdown tables with caption and label, included from
  the chapter.

``RUNS`` pins the run directory of each experiment, so the thesis only changes when a
run is replaced on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT_VARS = ROOT / "thesis" / "_variables.yml"
OUT_TABLES = ROOT / "thesis" / "_generated"

RUNS = {
    "m6_leaderboard": "2026-09-29_4de5c39",
    "significance_p1": "2026-10-02_d533687",
    "rps_vs_ir_p1": "2026-10-01_f7bdb95",
    "wound_ignite_p1": "2026-10-02_e33f242",
    "data_quality": "2026-11-09_17793ac",
    "finqboost": "2026-11-09_f70d879",
    "adagaussmc": "2026-11-09_17793ac",
    "model_comparison": "2026-11-09_fcfb4ef",
    "sensitivity_d4": "2026-11-09_c4359e5",
    "cascade": "2026-11-10_8491cc6",
}

# experiment key in the comparison -> name in the thesis, in table order
MODELS = {
    "baselines": "Frecuencia histórica",
    "finqboost": "FinQBoost",
    "wound_ignite": "wound-ignite",
    "adagaussmc": "AdaGaussMC (según el artículo)",
    "gbm": "GBM multiclase",
    "covsim": "Simulación desde covarianzas",
    "timesfm": "TimesFM-3",
}
WEIGHTINGS = {
    "uniform": "Benchmark (pesos iguales)",
    "wound_ignite": "wound-ignite (pesos del método)",
    "gbm_expected_rank": "GBM multiclase (quintil esperado)",
    "timesfm3_expected_rank": "TimesFM-3 (quintil esperado)",
}


def run(name: str) -> Path:
    return RESULTS / name / RUNS[name]


def num(x: float, d: int = 4) -> str:
    return f"{x:.{d}f}".replace("-", "−")


def pval(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f} %"


def table(frame: pd.DataFrame, caption: str, label: str) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    align = "|" + "|".join(["---"] + ["---:"] * (frame.shape[1] - 1)) + "|"
    rows = ["| " + " | ".join(map(str, r)) + " |" for r in frame.to_numpy()]
    return "\n".join([head, align, *rows, "", f": {caption} {{#{label}}}", ""])


def cascade_figure(c: pd.DataFrame, path: Path) -> None:
    """Two panels from cascade.csv: RPS improvement over uniform and annualised Sharpe."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"wspace": 0.08})
    y = list(range(len(c)))[::-1]
    axes[0].barh(y, -c["rps_diff"], color="#4C6A92", height=0.6)
    axes[0].set_yticks(y, list(c["name"]), fontsize=9)
    axes[0].xaxis.set_major_locator(MultipleLocator(0.001))
    axes[0].set_xlabel("Mejora de RPS sobre el uniforme")
    axes[1].barh(y, c["sharpe"], color="#4C6A92", height=0.6)
    axes[1].axvline(c["sharpe_benchmark"].iloc[-1], color="#B5523B", linewidth=1.2, linestyle="--")
    axes[1].set_yticks(y, [])
    axes[1].set_xlabel("Sharpe anualizado (línea punteada: pesos iguales)")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=9)
    fig.savefig(path, dpi=200, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)


def main() -> None:
    v: dict[str, dict[str, str]] = {}

    # --- data quality
    dq = run("data_quality")
    cov = pd.read_csv(dq / "coverage.csv")
    off_p = pd.read_csv(dq / "vs_official_periods.csv")
    off_d = pd.read_csv(dq / "vs_official_daily.csv")
    yah_p = pd.read_csv(dq / "vs_yahoo_periods.csv")
    splits = pd.read_csv(dq / "splits.csv")
    v["datos"] = {
        "simbolos": str(len(cov)),
        "faltantes": str(int((cov["flag"].fillna("") == "missing").sum())),
        "splits": str(len(splits)),
        "splits_sin_ajustar": str(int((~splits["adjusted"]).sum())),
        "ohlc": str(len(pd.read_csv(dq / "ohlc.csv"))),
        "oficial_quintil_max": pct(off_p["share_different_quintile"].max()),
        "oficial_mediana_bp": num(off_d["median_abs_diff_bp"].median(), 2),
        "yahoo_quintil_max": pct(yah_p["share_different_quintile"].max()),
        "yahoo_quintil_medio": pct(yah_p["share_different_quintile"].mean(), 1),
        "yahoo_periodos": str(len(yah_p)),
    }

    # --- replication of the official evaluation
    checks = json.loads((run("m6_leaderboard") / "checks.json").read_text())
    ranks = ("mismatches_rps_rank", "mismatches_ir_rank", "mismatches_overall_rank")
    v["replica"] = {
        "filas_mes": str(checks["month"]["rows"]),
        "filas_trimestre": str(checks["quarter"]["rows"]),
        "equipos": str(checks["global"]["rows"]),
        "rangos_distintos": str(
            sum(checks[level][k] for level in ("month", "quarter", "global") for k in ranks)
        ),
        "mejor_rps": str(checks["paper_text"]["reproduced"]["better_rps"]),
        "mejor_ir": str(checks["paper_text"]["reproduced"]["better_ir"]),
        "mejor_ambos": str(checks["paper_text"]["reproduced"]["both"]),
    }

    # --- period 1: teams against uniform, and RPS vs IR among teams
    teams = pd.read_csv(run("significance_p1") / "summary.csv").set_index("family").loc["teams"]
    corr = pd.read_csv(run("rps_vs_ir_p1") / "correlations.csv").set_index("analysis")
    g = corr.loc["spearman_global_all"]
    v["equipos"] = {
        "n": str(int(teams["comparisons"])),
        "mejor_media": str(int(teams["mean_diff_below_zero"])),
        "sig_sin_ajuste": str(int(teams["significant_raw"])),
        "sig_holm": str(int(teams["significant_holm"])),
        "sig_bh": str(int(teams["significant_bh"])),
        "spearman": num(g["estimate"], 3),
        "spearman_ic": f"[{num(g['ci_low'], 2)}, {num(g['ci_high'], 2)}]",
        "spearman_p": pval(g["p_perm"]),
    }

    # --- models in both periods
    mc = run("model_comparison")
    sig = pd.read_csv(mc / "significance.csv")
    scores = pd.read_csv(mc / "scores.csv")
    by = {f: d.set_index("model") for f, d in sig.groupby("family")}
    p1, p2, p2b = by["period1"], by["period2"], by["period2_after_pretraining"]
    uni = scores[scores["model"] == "uniform"].set_index("phase")
    v["uniforme"] = {
        "rps_p1": num(uni.loc["period1", "rps"]),
        "rps_p2": num(uni.loc["period2", "rps"]),
        "n_p1": str(int(uni.loc["period1", "n_periods"])),
        "n_p2": str(int(uni.loc["period2", "n_periods"])),
        "n_p2_posterior": str(int(p2b["n_periods"].iloc[0])),
    }
    rows = []
    for key, name in MODELS.items():
        a, b = p1.loc[key], p2.loc[key]
        rows.append(
            [
                name,
                num(a["mean_rps_diff"], 5),
                pval(a["p_holm"]),
                num(b["mean_rps_diff"], 5),
                f"[{num(b['boot_ci_low'], 5)}, {num(b['boot_ci_high'], 5)}]",
                pct(b["share_periods_better"]),
                pval(b["p_holm"]),
            ]
        )
        v[key] = {
            "dif_p1": num(a["mean_rps_diff"], 4),
            "dif_p2": num(b["mean_rps_diff"], 4),
            "rel_p2": pct(-b["mean_rps_diff"] / uni.loc["period2", "rps"], 1),
            "holm_p1": pval(a["p_holm"]),
            "holm_p2": pval(b["p_holm"]),
            "mejor_p2": pct(b["share_periods_better"]),
            "holm_p2_posterior": pval(p2b.loc[key, "p_holm"]),
            "dif_p2_posterior": num(p2b.loc[key, "mean_rps_diff"], 4),
        }
    cols = [
        "Modelo",
        "Dif. RPS, periodo 1",
        "p (Holm)",
        "Dif. RPS, periodo 2",
        "IC 95 % bootstrap",
        "Periodos mejores",
        "p (Holm) ",
    ]
    OUT_TABLES.mkdir(exist_ok=True)
    caption = (
        "Diferencia media de RPS de cada modelo contra el pronóstico uniforme (negativa = "
        "mejor que el uniforme), con la prueba de Diebold y Mariano ajustada por Holm."
    )
    (OUT_TABLES / "tbl-significancia.md").write_text(
        table(pd.DataFrame(rows, columns=cols), caption, "tbl-significancia"), encoding="utf-8"
    )
    better = [k for k in MODELS if p2.loc[k, "p_holm"] < 0.05]
    v["modelos"] = {
        "n": str(len(MODELS)),
        "sig_p2": str(len(better)),
        "sig_p1": str(int((p1.loc[list(MODELS), "p_holm"] < 0.05).sum())),
        "mejor_dif_p2": num(p2.loc[list(MODELS), "mean_rps_diff"].min(), 4),
        "mejor_rel_p2": pct(
            -p2.loc[list(MODELS), "mean_rps_diff"].min() / uni.loc["period2", "rps"], 1
        ),
    }

    # --- investment: IR of the weightings that differ from the benchmark
    s = scores.set_index(["model", "phase"])
    rows = [
        [
            name,
            *(num(s.loc[(m, ph), c], 2) for ph in ("period1", "period2") for c in ("ir", "ir_net")),
        ]
        for m, name in WEIGHTINGS.items()
    ]
    cols = ["Portafolio", "IR, periodo 1", "IR neto", "IR, periodo 2", "IR neto "]
    caption = (
        "IR agregado de cada portafolio, bruto y neto de costos de 10 pb sobre la rotación. "
        "Los modelos que no aparecen invierten con pesos iguales y coinciden con el benchmark."
    )
    (OUT_TABLES / "tbl-ir.md").write_text(
        table(pd.DataFrame(rows, columns=cols), caption, "tbl-ir"), encoding="utf-8"
    )
    r = pd.read_csv(mc / "rps_vs_ir.csv").set_index("y").loc["ir_net"]
    v["inversion"] = {
        "ir_bench_p2": num(s.loc[("uniform", "period2"), "ir_net"], 2),
        "mejores_que_bench_p2": str(
            sum(
                s.loc[(m, "period2"), "ir_net"] > s.loc[("uniform", "period2"), "ir_net"]
                for m in WEIGHTINGS
                if m != "uniform"
            )
        ),
        "activos": str(len(WEIGHTINGS) - 1),
        "spearman_modelos": num(r["estimate"], 2),
        "spearman_modelos_ic": f"[{num(r['ci_low'], 2)}, {num(r['ci_high'], 2)}]",
        "spearman_modelos_n": str(int(r["n"])),
    }

    # --- persistence (RQ1) and fidelity
    pers = pd.read_csv(mc / "persistence.csv").set_index("method")
    fid = {k: pd.read_csv(run(k) / "fidelity.csv") for k in ("finqboost", "adagaussmc")}
    rows = []
    for key in pers.index:
        f = fid.get(key)
        rows.append(
            [
                MODELS[key],
                "—" if f is None else num(f["corr"].mean(), 2),
                num(pers.loc[key, "rps_diff_period1"], 5),
                num(pers.loc[key, "rps_diff_period2"], 5),
                pval(pers.loc[key, "p_holm_period2"]),
                pers.loc[key, "verdict"],
            ]
        )
    cols = [
        "Método",
        "Correlación con sus envíos",
        "Dif. RPS, periodo 1",
        "Dif. RPS, periodo 2",
        "p (Holm), periodo 2",
        "Conclusión",
    ]
    caption = (
        "Persistencia de los métodos de equipos de la M6: diferencia de RPS contra el uniforme "
        "en la competencia (periodo 1) y después de ella (periodo 2)."
    )
    (OUT_TABLES / "tbl-persistencia.md").write_text(
        table(pd.DataFrame(rows, columns=cols), caption, "tbl-persistencia"), encoding="utf-8"
    )
    for key, f in fid.items():
        v[key].update(
            {
                "fid_corr": num(f["corr"].mean(), 2),
                "fid_corr_final": num(f[f["k"] >= 6]["corr"].mean(), 2),
                "fid_rps_equipo": num(f["rps_submission"].mean()),
                "fid_rps_propio": num(f["rps_reproduction"].mean()),
            }
        )
    wi = pd.read_csv(run("wound_ignite_p1") / "fidelity.csv")
    v["wound_ignite"]["fid_corr_mes10"] = num(wi[wi["k"] == 10]["corr"].mean(), 2)

    # --- sensitivity D4: period 2 with the official universe rule
    d4 = pd.read_csv(run("sensitivity_d4") / "summary.csv").set_index("model")
    change = (d4["mean_rps_diff"] - p2.loc[d4.index, "mean_rps_diff"]).abs()
    v["d4"] = {
        "sig": str(int((d4["p_holm"] < 0.05).sum())),
        "n": str(len(d4)),
        "cambio_max": num(change.max(), 4),
        "mismos": "los mismos" if set(d4.index[d4["p_holm"] < 0.05]) == set(better) else "otros",
    }

    # --- bias cascade (RQ4)
    if RUNS["cascade"]:
        c = pd.read_csv(run("cascade") / "cascade.csv").set_index("step")
        rows = [
            [
                r["name"],
                num(r["rps_diff"], 5),
                pval(r["p_dm"]),
                num(r["ir"], 1),
                num(r["sharpe"], 2),
                pct(r["turnover"]),
            ]
            for _, r in c.iterrows()
        ]
        cols = ["Paso", "Dif. RPS", "p", "IR", "Sharpe anual", "Rotación media"]
        caption = (
            "Cascada de sesgos sobre el gradient boosting en el periodo 2. Cada paso agrega una "
            "corrección a las anteriores. La diferencia de RPS es contra el uniforme en el mismo "
            "universo; el último paso es neto de costos."
        )
        (OUT_TABLES / "tbl-cascada-resultados.md").write_text(
            table(pd.DataFrame(rows, columns=cols), caption, "tbl-cascada-resultados"),
            encoding="utf-8",
        )
        cascade_figure(c, OUT_TABLES / "fig-cascada.png")
        search = pd.read_csv(run("cascade") / "search.csv")
        v["cascada"] = {
            "configuraciones": str(int(search.groupby("step").size().iloc[0])),
            "sharpe_bench": num(c.loc["s6", "sharpe_benchmark"], 2),
            "sharpe_bench_s0": num(c.loc["s0", "sharpe_benchmark"], 2),
            "veces_bench_s0": num(c.loc["s0", "sharpe"] / c.loc["s0", "sharpe_benchmark"], 1),
            "ir_bench": num(c.loc["s6", "ir_benchmark"], 1),
            **{f"dif_{k}": num(c.loc[k, "rps_diff"], 4) for k in c.index},
            **{f"sharpe_{k}": num(c.loc[k, "sharpe"], 2) for k in c.index},
            **{f"ir_{k}": num(c.loc[k, "ir"], 1) for k in c.index},
            **{f"p_{k}": pval(c.loc[k, "p_dm"]) for k in c.index},
            "caida_rps": num(c.loc["s6", "rps_diff"] - c.loc["s0", "rps_diff"], 4),
            "caida_sharpe": num(c.loc["s0", "sharpe"] - c.loc["s6", "sharpe"], 2),
        }

    lines = ["# Generated by scripts/build_thesis_results.py from results/. Do not edit."]
    for group, values in v.items():
        lines.append(f"{group}:")
        lines += [f'  {k}: "{val}"' for k, val in values.items()]
    OUT_VARS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT_VARS.name}: {sum(len(x) for x in v.values())} values")
    print(f"{OUT_TABLES.name}: {len(list(OUT_TABLES.glob('*.md')))} tables")


if __name__ == "__main__":
    main()
