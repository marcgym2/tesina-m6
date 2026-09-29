"""Reproduction of the official M6 leaderboard and of the paper's figures (issue #10)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tesina.data import m6
from tesina.evaluation import leaderboard as lb

PAPER_TABLE4 = Path(__file__).parent / "data" / "m6_paper_table4.csv"
SCORE_TOL = 6e-6  # the official leaderboard is rounded to 5 decimals
RANK_COLUMNS = ["rps_rank", "ir_rank", "overall_rank", "position"]


@pytest.fixture(scope="module")
def scores():
    return lb.score_submissions(m6.load_submissions(), m6.load_assets(), m6.load_period1_calendar())


def _compare(mine: pd.DataFrame, official: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    merged = official.merge(mine, on=keys, how="outer", suffixes=("_off", ""), indicator=True)
    assert (merged["_merge"] == "both").all(), merged.loc[merged["_merge"] != "both", keys]
    return merged


@pytest.mark.parametrize("level", ["month", "quarter", "global"])
def test_scores_and_ranks_match_official(scores, level):
    mine = lb.leaderboard(scores, level)
    official = m6.load_leaderboard(level)
    if level == "month":
        official = official[official["evaluation"] != m6.EVALUATIONS[0]].copy()
        official["period"] = official["evaluation"].map(
            {e: i for i, e in enumerate(m6.EVALUATIONS)}
        )
    keys = ["team"] if level == "global" else ["team", "period"]
    merged = _compare(mine, official, keys)
    assert (merged["rps"] - merged["rps_off"]).abs().max() < SCORE_TOL
    assert (merged["ir"] - merged["ir_off"]).abs().max() < SCORE_TOL
    for col in RANK_COLUMNS:
        assert (merged[col] == merged[f"{col}_off"]).all(), col


def test_inclusion_rules(scores):
    """Inactive teams are excluded; aggregates need a score in their first month."""
    subs = m6.load_submissions()
    inactive = set(subs.loc[subs["IsActive"] == 0, "Team"])
    assert not inactive & {t for t, _ in scores.rps}
    glob = lb.leaderboard(scores, "global")
    assert len(glob) == 163
    assert set(glob["team"]) == set(scores.teams(lb.MONTHS[0]))
    quarters = lb.leaderboard(scores, "quarter").groupby("period").size()
    assert quarters.tolist() == [163, 197, 208, 223]


def test_paper_global_counts(scores):
    """arXiv:2310.13357v1: of 163 teams, 38 beat the benchmark in RPS, 47 in IR, 11 both."""
    glob = lb.summarize(scores, lb.MONTHS).set_index("team")
    bench_ir = glob.loc[lb.BENCHMARK_TEAM, "ir"]
    # Uniform forecasts score 0.16 up to floating-point noise.
    better_rps = glob["rps"].round(lb.RPS_RANK_DECIMALS) < 0.16
    better_ir = glob["ir"] > bench_ir
    assert len(glob) == 163
    assert (better_rps.sum(), better_ir.sum(), (better_rps & better_ir).sum()) == (38, 47, 11)
    assert bench_ir == pytest.approx(0.453, abs=5e-4)


def test_paper_table4_reproduced(scores):
    paper = pd.read_csv(PAPER_TABLE4, comment="#").set_index("period")
    mine = lb.paper_table4(scores, compare_to="global").set_index("period")
    assert (mine["n_teams"] == 148).all()
    pct = ["better_returns_pct", "better_risk_pct", "better_ir_pct"]
    np.testing.assert_allclose(mine[pct].round(2), paper[pct], atol=1e-9)
    rest = [c for c in paper.columns if c not in pct]
    np.testing.assert_allclose(mine[rest].round(3), paper[rest], atol=1e-9)


def test_paper_table4_corrected_differs(scores):
    """Comparing each month with that month's benchmark changes the shares a lot."""
    script = lb.paper_table4(scores, compare_to="global").set_index("period")
    corrected = lb.paper_table4(scores, compare_to="period").set_index("period")
    assert corrected.loc["Global", "better_ir_pct"] == pytest.approx(
        script.loc["Global", "better_ir_pct"]
    )
    months = lb.MONTHS
    assert (
        corrected.loc[months, "better_ir_pct"] - script.loc[months, "better_ir_pct"]
    ).abs().max() > 30
