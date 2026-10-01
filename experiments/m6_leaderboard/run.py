"""Reproduce the official M6 leaderboard and the paper's Table 4 (issue #10).

    uv run python experiments/m6_leaderboard/run.py

Writes results/m6_leaderboard/<date>_<commit>/:
- monthly.csv, quarterly.csv, global.csv: reproduced scores and ranks next to the
  official ones (``*_official``); ``ir_code`` is the IR with the published code's
  zero-variance rule (NaN), ``ir`` the leaderboard's (1.0).
- paper_table4_script.csv: Table 4 as computed by Hypothesis1.R (arXiv:2310.13357v1).
- paper_table4_corrected.csv: same, each month compared with that month's benchmark.
- checks.json: summary of every comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tesina.data import m6
from tesina.evaluation import leaderboard as lb
from tesina.experiment import load_config, prepare_run

HERE = Path(__file__).resolve().parent
PAPER_TABLE4 = m6.REPO_ROOT / "tests" / "data" / "m6_paper_table4.csv"
RANKS = ["rps_rank", "ir_rank", "overall_rank", "position"]


def compare(level: str, scores: lb.Scores, zero_variance: float) -> tuple[pd.DataFrame, dict]:
    mine = lb.leaderboard(scores, level, zero_variance=zero_variance)
    code = lb.leaderboard(scores, level, zero_variance=float("nan"), ranked=False)
    keys = ["team"] if level == "global" else ["team", "period"]
    mine = mine.merge(code[[*keys, "ir"]].rename(columns={"ir": "ir_code"}), on=keys)
    official = m6.load_leaderboard(level)
    if level == "month":
        official = official[official["evaluation"] != m6.EVALUATIONS[0]].copy()
        official["period"] = official["evaluation"].map(
            {e: i for i, e in enumerate(m6.EVALUATIONS)}
        )
        official = official.drop(columns="evaluation")
    table = mine.merge(official, on=keys, how="outer", suffixes=("", "_official"))
    check = {
        "rows": len(table),
        "missing_in_reproduction": int(table["rps"].isna().sum()),
        "missing_in_official": int(table["rps_official"].isna().sum()),
        "max_abs_diff_rps": float((table["rps"] - table["rps_official"]).abs().max()),
        "max_abs_diff_ir": float((table["ir"] - table["ir_official"]).abs().max()),
        **{
            f"mismatches_{col}": int((table[col] != table[f"{col}_official"]).sum())
            for col in RANKS
        },
    }
    return table, check


def main() -> None:
    config = load_config(HERE / "config.toml")
    out = prepare_run("m6_leaderboard", HERE / "config.toml")
    snapshot = config["data"]["snapshot"]
    zero_variance = config["evaluation"]["zero_variance_leaderboard"]

    scores = lb.score_submissions(
        m6.load_submissions(snapshot), m6.load_assets(snapshot), m6.load_period1_calendar(snapshot)
    )
    checks = {}
    for level, filename in (("month", "monthly"), ("quarter", "quarterly"), ("global", "global")):
        table, checks[level] = compare(level, scores, zero_variance)
        table.to_csv(out / f"{filename}.csv", index=False)

    glob = lb.summarize(scores, lb.MONTHS).set_index("team")
    bench_ir = glob.loc[config["evaluation"]["benchmark_team"], "ir"]
    better_rps = glob["rps"].round(lb.RPS_RANK_DECIMALS) < 0.16
    better_ir = glob["ir"] > bench_ir
    checks["paper_text"] = {
        "source": "arXiv:2310.13357v1, section on global performance",
        "published": {"teams": 163, "better_rps": 38, "better_ir": 47, "both": 11},
        "reproduced": {
            "teams": len(glob),
            "better_rps": int(better_rps.sum()),
            "better_ir": int(better_ir.sum()),
            "both": int((better_rps & better_ir).sum()),
        },
    }

    paper = pd.read_csv(PAPER_TABLE4, comment="#").set_index("period")
    script = lb.paper_table4(scores, compare_to="global").set_index("period")
    corrected = lb.paper_table4(scores, compare_to="period").set_index("period")
    script.to_csv(out / "paper_table4_script.csv")
    corrected.to_csv(out / "paper_table4_corrected.csv")
    pct = ["better_returns_pct", "better_risk_pct", "better_ir_pct"]
    rest = [c for c in paper.columns if c not in pct]
    checks["paper_table4"] = {
        "source": "arXiv:2310.13357v1, Table 4",
        "max_abs_diff_pct_rounded_2": float((script[pct].round(2) - paper[pct]).abs().max().max()),
        "max_abs_diff_other_rounded_3": float(
            (script[rest].round(3) - paper[rest]).abs().max().max()
        ),
    }
    (out / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))
    print(f"results in {out.relative_to(m6.REPO_ROOT)}")


if __name__ == "__main__":
    main()
